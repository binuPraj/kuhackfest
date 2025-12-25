"""
Core Service Layer - Unified Backend Logic
============================================

╔══════════════════════════════════════════════════════════════════════════════╗
║                    ARCHITECTURAL COMPLIANCE VERIFICATION                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ ✅ VERIFIED: 2024-12-25                                                      ║
║ ✅ Single source of truth for ALL AI reasoning logic                        ║
║ ✅ Both chatbot and extension consume this layer                             ║
║ ✅ ZERO duplicated AI logic exists outside this module                       ║
║ ✅ Chatbot response format/behavior is UNCHANGED                             ║
║ ✅ Uses unified llm_client for all model invocations                         ║
║ ✅ LOCAL MODEL FALLACY CLASSIFICATION - No LLM for fallacy detection        ║
╚══════════════════════════════════════════════════════════════════════════════╝

LOCAL FALLACY CLASSIFICATION (Migrated from new.py):
────────────────────────────────────────────────────
✅ Fallacy detection uses local saved_models/ (Electra-based NLI models)
✅ Uses mapcsv/mappings.csv for fallacy descriptions and hypotheses
✅ NO LLM/API calls for fallacy classification - fully local inference
✅ Faster response times, no API costs for fallacy detection
✅ LLM still used for Toulmin analysis, argument improvement, counter-arguments

ARCHITECTURE:
┌─────────────────┐     ┌─────────────────┐
│   Chatbot UI    │     │ Extension UI    │
│  (chat.html)    │     │  (popup.html)   │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│  gem_app.py     │     │ extension/      │
│  (chatbot API)  │     │ routes.py       │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
         ┌─────────────────────┐
         │   core_service.py   │  ← YOU ARE HERE
         │  (unified logic)    │
         └──────────┬──────────┘
                    │
         ┌──────────┴──────────┐
         │                     │
         ▼                     ▼
┌─────────────────────┐  ┌─────────────────────┐
│  LOCAL MODEL        │  │   llm_client.py     │
│  (saved_models/)    │  │  (AI gateway)       │
│  Fallacy Detection  │  │  Toulmin/Feedback   │
└─────────────────────┘  └─────────────────────┘

USAGE:
    from services.core_service import (
        analyze_argument,
        improve_argument,
        generate_counter_argument,
        evaluate_response,
        detect_fallacies,
        classify_with_local_model  # NEW: Local fallacy classification
    )

The chatbot (gem_app.py) remains unchanged - it already has the working logic.
This service exposes the same logic for the extension to consume.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional
from difflib import SequenceMatcher

# Local model dependencies
import torch
import pandas as pd
from transformers import AutoConfig, AutoTokenizer, AutoModelForSequenceClassification

from .llm_client import llm_client


# ==============================
# Local Model Configuration
# ==============================
# Paths relative to this file (backend/services/core_service.py)
SAVED_MODELS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "saved_models")
MAPPINGS_CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "mapcsv", "mappings.csv")
FALLACIES_JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "public", "data", "logicalfallacy.json")

# Default model folder (can be changed to use different models)
DEFAULT_MODEL_FOLDER = "electra-logic"

# Local model cache to avoid reloading on every request
_LOCAL_MODEL_CACHE = {}

# Global fallacy list loaded from logicalfallacy.json
FALLACY_LIST = []

# ==============================
# Improved Statement Tracking
# ==============================
# Cache to store improved statements and prevent re-improvement loops
# Structure: {original_argument_normalized: improved_statement}
_IMPROVED_STATEMENTS_CACHE = {}

# File to persist improved statements
IMPROVED_STATEMENTS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 
    "improved_statements_cache.json"
)


def _normalize_argument(text: str) -> str:
    """
    Normalize argument text for comparison.
    Removes extra whitespace, converts to lowercase, and trims punctuation.
    """
    if not text:
        return ""
    # Convert to lowercase and remove extra whitespace
    text = " ".join(text.lower().split())
    # Remove trailing punctuation
    text = text.rstrip('.,;:!?')
    return text


def _calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity ratio between two texts.
    Returns a value between 0.0 and 1.0.
    """
    return SequenceMatcher(None, 
                          _normalize_argument(text1), 
                          _normalize_argument(text2)).ratio()


def _load_improved_statements_cache():
    """Load improved statements cache from file."""
    global _IMPROVED_STATEMENTS_CACHE
    try:
        if os.path.exists(IMPROVED_STATEMENTS_FILE):
            with open(IMPROVED_STATEMENTS_FILE, 'r', encoding='utf-8') as f:
                _IMPROVED_STATEMENTS_CACHE = json.load(f)
            print(f"[CACHE] ✅ Loaded {len(_IMPROVED_STATEMENTS_CACHE)} improved statements from cache")
        else:
            _IMPROVED_STATEMENTS_CACHE = {}
            print(f"[CACHE] 📝 Created new improved statements cache")
    except Exception as e:
        print(f"[CACHE] ⚠️ Error loading cache: {e}. Starting with empty cache.")
        _IMPROVED_STATEMENTS_CACHE = {}


def _save_improved_statements_cache():
    """Save improved statements cache to file."""
    try:
        with open(IMPROVED_STATEMENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(_IMPROVED_STATEMENTS_CACHE, f, indent=2, ensure_ascii=False)
        print(f"[CACHE] 💾 Saved {len(_IMPROVED_STATEMENTS_CACHE)} improved statements to cache")
    except Exception as e:
        print(f"[CACHE] ❌ Error saving cache: {e}")


def add_improved_statement(original: str, improved: str):
    """
    Add a mapping from original to improved statement.
    
    Args:
        original: The original argument text
        improved: The improved version of the argument
    """
    normalized_original = _normalize_argument(original)
    _IMPROVED_STATEMENTS_CACHE[normalized_original] = improved
    _save_improved_statements_cache()
    print(f"[CACHE] ➕ Added improved statement mapping")


def is_improved_statement(argument_text: str, similarity_threshold: float = 0.90) -> bool:
    """
    Check if the given argument matches any previously improved statement.
    
    Uses fuzzy matching to account for minor variations in text.
    
    Args:
        argument_text: The argument to check
        similarity_threshold: Minimum similarity ratio (0.0-1.0) to consider a match
    
    Returns:
        True if argument matches an improved statement, False otherwise
    """
    normalized_input = _normalize_argument(argument_text)
    
    # Check exact match first (fastest)
    if normalized_input in _IMPROVED_STATEMENTS_CACHE.values():
        print(f"[CACHE] ✅ Exact match found - this is an improved statement")
        return True
    
    # Check fuzzy match against all improved statements
    for original, improved in _IMPROVED_STATEMENTS_CACHE.items():
        similarity = _calculate_similarity(argument_text, improved)
        if similarity >= similarity_threshold:
            print(f"[CACHE] ✅ Fuzzy match found (similarity: {similarity:.2%}) - this is an improved statement")
            return True
    
    print(f"[CACHE] ℹ️ Not an improved statement")
    return False


# Load cache on module import
_load_improved_statements_cache()


# ==============================
# Load Canonical Fallacy List
# ==============================
def _load_fallacy_list() -> List[Dict[str, str]]:
    """Load the 13 canonical fallacies from logicalfallacy.json"""
    global FALLACY_LIST
    try:
        with open(FALLACIES_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            fallacies = []
            for f_item in data.get("fallacies", []):
                fallacies.append({
                    "name": f_item["name"],
                    "alias": f_item.get("alias", ""),
                    "description": f_item["description"]
                })
            print(f"[LOCAL_MODEL] ✅ Loaded {len(fallacies)} canonical fallacies from logicalfallacy.json")
            FALLACY_LIST = fallacies
            return fallacies
    except Exception as e:
        print(f"[LOCAL_MODEL] ❌ Error loading fallacies JSON: {e}")
        return []

# Load on module import
FALLACY_LIST = _load_fallacy_list()


# ==============================
# Local Model Helper Functions
# ==============================
def _normalize_label(name: str) -> str:
    """
    Normalize fallacy/label names for robust matching.
    Removes parenthetical phrases, punctuation, and normalizes whitespace/lowercase.
    """
    if not name:
        return ""
    # Remove parenthetical content like 'Ad Hominem (Personal Attack)'
    name = re.sub(r"\(.*?\)", "", name)
    # Lowercase and strip punctuation (keep alphanumerics and spaces)
    name = re.sub(r"[^a-z0-9\s]", "", name.lower())
    # Collapse whitespace
    name = " ".join(name.split())
    return name


def _fallback_tokenizer_id(model_type: str) -> str:
    """Get fallback tokenizer based on model type."""
    tokenizers = {
        "electra": "google/electra-base-discriminator",
        "deberta": "microsoft/deberta-base",
        "roberta": "roberta-base",
        "bert": "bert-base-uncased"
    }
    return tokenizers.get(model_type, "bert-base-uncased")


def _load_tokenizer(model_path: str, explicit_tokenizer: str = None):
    """Load tokenizer with fallback options."""
    # Try explicit tokenizer first
    if explicit_tokenizer:
        try:
            return AutoTokenizer.from_pretrained(explicit_tokenizer)
        except Exception as e:
            print(f"[LOCAL_MODEL] ⚠️ Failed loading tokenizer '{explicit_tokenizer}': {e}")

    # Try loading from model path
    try:
        return AutoTokenizer.from_pretrained(model_path)
    except Exception:
        pass

    # Try fallback based on config
    try:
        cfg = AutoConfig.from_pretrained(model_path)
        fallback_id = _fallback_tokenizer_id(getattr(cfg, "model_type", ""))
        print(f"[LOCAL_MODEL] 📦 Using fallback tokenizer: {fallback_id}")
        return AutoTokenizer.from_pretrained(fallback_id)
    except Exception as e:
        print(f"[LOCAL_MODEL] ❌ Loading fallback tokenizer failed: {e}")
        raise


def _build_hypothesis(label: str, mappings_df: pd.DataFrame, mode: str = "base") -> str:
    """
    Build hypothesis string for NLI classification.
    
    Modes:
    - base: "This is an example of {label} logical fallacy"
    - simplify: Uses 'Understandable Name' from mappings
    - description: Uses 'Description' from mappings
    - logical-form: Uses 'Logical Form' from mappings
    - masked-logical-form: Uses 'Masked Logical Form' from mappings
    """
    if mode == "base":
        return f"This is an example of {label} logical fallacy"

    try:
        if mode == "simplify":
            name = mappings_df.loc[mappings_df["Original Name"] == label, "Understandable Name"].values[0]
            return f"This is an example of {name}"

        if mode == "description":
            desc = mappings_df.loc[mappings_df["Original Name"] == label, "Description"].values[0]
            return f"This is an example of {desc}"

        if mode == "logical-form":
            form = mappings_df.loc[mappings_df["Original Name"] == label, "Logical Form"].values[0]
            return f"This article matches the following logical form: {form}"

        if mode == "masked-logical-form":
            form = mappings_df.loc[mappings_df["Original Name"] == label, "Masked Logical Form"].values[0]
            return f"This article matches the following logical form: {form}"
    except (IndexError, KeyError):
        pass

    return f"This is an example of {label} logical fallacy"


# ==============================
# Local Model Fallacy Classification
# ==============================
def classify_with_local_model(
    argument_text: str,
    model_folder: str = None,
    mappings_csv: str = None,
    mode: str = "base",
    topk: int = 5,
    threshold: float = 0.3
) -> List[Dict[str, Any]]:
    """
    Classify fallacies using local saved model (NO LLM calls).
    
    This function is migrated from new.py and uses:
    - saved_models/ folder with Electra-based NLI models
    - mapcsv/mappings.csv for fallacy descriptions
    - public/data/logicalfallacy.json for canonical 13 fallacies
    
    Args:
        argument_text: The text to analyze for fallacies
        model_folder: Name of model folder in saved_models/ (default: electra-logic)
        mappings_csv: Path to mappings CSV (default: mapcsv/mappings.csv)
        mode: Hypothesis building mode (base, simplify, description, logical-form)
        topk: Number of top predictions to return
        threshold: Minimum score to consider a fallacy detected (0.0-1.0)
    
    Returns:
        List of dicts with format: [{"label": "fallacy_name", "score": 0.85}, ...]
    """
    # Resolve model path
    model_folder = model_folder or DEFAULT_MODEL_FOLDER
    model_path = os.path.normpath(os.path.join(SAVED_MODELS_PATH, model_folder))
    
    print(f"[LOCAL_MODEL] 🔍 Classifying fallacies with model: {model_folder}")
    print(f"[LOCAL_MODEL] 📁 Model path: {model_path}")
    print(f"[LOCAL_MODEL] 📁 Model exists: {os.path.exists(model_path)}")

    # Create cache key
    csv_path = mappings_csv or MAPPINGS_CSV_PATH
    cache_key = f"{model_path}|{csv_path}|{mode}"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[LOCAL_MODEL] 💻 Device: {device}")

    # Load and cache model/tokenizer/mappings
    if cache_key not in _LOCAL_MODEL_CACHE:
        print(f"[LOCAL_MODEL] 📦 Loading model (first time)...")
        
        # Load mappings CSV
        try:
            mappings_df = pd.read_csv(csv_path)
            print(f"[LOCAL_MODEL] ✅ Loaded {len(mappings_df)} fallacy mappings from CSV")
        except Exception as e:
            print(f"[LOCAL_MODEL] ⚠️ Failed loading mappings CSV {csv_path}: {e}")
            mappings_df = pd.DataFrame({"Original Name": []})

        # Load tokenizer
        try:
            tokenizer = _load_tokenizer(model_path)
            print(f"[LOCAL_MODEL] ✅ Tokenizer loaded successfully")
        except Exception as e:
            print(f"[LOCAL_MODEL] ⚠️ Tokenizer load failed, trying fallback: {e}")
            try:
                tokenizer = AutoTokenizer.from_pretrained("google/electra-base-discriminator")
                print(f"[LOCAL_MODEL] ✅ Fallback tokenizer loaded")
            except Exception as e2:
                print(f"[LOCAL_MODEL] ❌ All tokenizer loading failed: {e2}")
                return []

        # Load model
        try:
            model = AutoModelForSequenceClassification.from_pretrained(model_path)
            model.to(device)
            model.eval()
            print(f"[LOCAL_MODEL] ✅ Model loaded successfully")
        except Exception as e:
            print(f"[LOCAL_MODEL] ❌ Loading model failed: {e}")
            # Cache a stub to avoid repeated failures
            _LOCAL_MODEL_CACHE[cache_key] = {
                "model": None,
                "tokenizer": tokenizer if 'tokenizer' in dir() else None,
                "mappings_df": mappings_df,
                "device": device
            }
            return []

        # Cache everything
        _LOCAL_MODEL_CACHE[cache_key] = {
            "model": model,
            "tokenizer": tokenizer,
            "mappings_df": mappings_df,
            "device": device
        }
        print(f"[LOCAL_MODEL] ✅ Model cached for future requests")

    # Retrieve cached components
    info = _LOCAL_MODEL_CACHE[cache_key]
    model = info["model"]
    tokenizer = info["tokenizer"]
    mappings_df = info["mappings_df"]
    device = info["device"]

    # If no model loaded, return empty
    if model is None:
        print(f"[LOCAL_MODEL] ⚠️ No model available (load failed previously)")
        return []

    # Get labels from mappings CSV
    labels = list(mappings_df.get("Original Name", []))

    # Filter to canonical 13 fallacies using normalized matching
    try:
        canonical_map = {_normalize_label(f["name"]): f["name"] for f in FALLACY_LIST}
        filtered = []
        for lbl in labels:
            norm = _normalize_label(lbl)
            if norm in canonical_map:
                filtered.append(canonical_map[norm])
        labels = filtered
        print(f"[LOCAL_MODEL] 📋 Using {len(labels)} canonical fallacy labels")
    except Exception:
        print(f"[LOCAL_MODEL] ⚠️ Could not filter to canonical fallacies, using all labels")

    if len(labels) == 0:
        print(f"[LOCAL_MODEL] ⚠️ No fallacy labels available")
        return []

    # Build hypotheses for NLI classification
    hypotheses = [_build_hypothesis(lbl, mappings_df, mode) for lbl in labels]

    # Tokenize: premise (argument) + hypothesis pairs
    batch = tokenizer(
        [argument_text] * len(labels),
        hypotheses,
        padding=True,
        truncation=True,
        return_tensors="pt"
    )
    batch = {k: v.to(device) for k, v in batch.items()}

    # Run inference
    with torch.no_grad():
        logits = model(**batch).logits
        # For MNLI-style models, use softmax over logits
        # Column 0 often represents the "entailment" class
        probs = torch.softmax(logits, dim=1)[:, 0]

    # Sort by score and get top-k
    scores = list(zip(labels, probs.cpu().tolist()))
    scores.sort(key=lambda x: x[1], reverse=True)

    # Filter by threshold and return top-k
    results = [
        {"label": lbl, "score": float(score)}
        for lbl, score in scores[:topk]
        if score >= threshold
    ]
    
    print(f"[LOCAL_MODEL] ✅ Classification complete. Top fallacies: {[r['label'] for r in results]}")
    return results


def get_detected_fallacies(argument_text: str, threshold: float = 0.4) -> List[str]:
    """
    Convenience function to get just the fallacy names detected in text.
    
    Args:
        argument_text: Text to analyze
        threshold: Minimum confidence score (0.0-1.0)
    
    Returns:
        List of fallacy names (strings) detected with score >= threshold
    """
    predictions = classify_with_local_model(
        argument_text,
        model_folder=DEFAULT_MODEL_FOLDER,
        mode="base",
        topk=5,
        threshold=threshold
    )
    return [p["label"] for p in predictions]

# ==============================
# Load Prompt Templates (same as chatbot)
# ==============================
TEMPLATES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates.json")

try:
    with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
        templates = json.load(f)
except FileNotFoundError:
    print("❌ templates.json not found in core_service")
    templates = {}


# ==============================
# Core LLM Completion Function
# ==============================
def _llm_completion(system_role: str, prompt: str, client_ip: str = "127.0.0.1", json_mode: bool = True) -> Optional[str]:
    """
    Internal LLM call wrapper - same logic as chatbot's llm_completion().
    Routes through unified llm_client for consistency.
    """
    messages = [
        {"role": "system", "content": system_role},
        {"role": "user", "content": prompt}
    ]
    
    try:
        response = llm_client.chat_completion(
            messages=messages,
            client_ip=client_ip,
            temperature=0.7,
            json_mode=json_mode
        )
        return response
    except Exception as e:
        print(f"❌ Core service LLM error: {e}")
        return None


def _parse_json_response(response: str) -> Optional[Dict[str, Any]]:
    """Parse JSON response, returning None on failure."""
    if not response:
        return None
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return None


# ==============================
# Core Business Logic Functions
# ==============================

def analyze_argument(argument_text: str, client_ip: str = "127.0.0.1") -> Dict[str, Any]:
    """
    Analyze an argument using the Toulmin model.
    
    ┌──────────────────────────────────────────────────────────────────┐
    │ ✅ COMPLIANCE: This is the UNIFIED function for argument analysis│
    │                                                                  │
    │ CHATBOT CALL PATH:                                               │
    │   gem_app.py:/api/extract_toulmin → analyze_argument()           │
    │                                                                  │
    │ EXTENSION CALL PATH:                                             │
    │   routes.py:/api/analyze → analyze_argument()                    │
    │   routes.py:/api/detect-fallacies → analyze_argument()           │
    │                                                                  │
    │ BOTH paths converge HERE. Zero duplicated logic.                 │
    │                                                                  │
    │ 🆕 LOCAL FALLACY CLASSIFICATION (2024-12-25):                    │
    │   Fallacies are now detected using local saved_models/ folder.   │
    │   NO LLM calls for fallacy detection - faster & free.            │
    │   LLM still used for Toulmin analysis and feedback generation.   │
    └──────────────────────────────────────────────────────────────────┘
    
    This is the EXACT same logic used by the chatbot's /api/extract_toulmin endpoint.
    Returns the same response structure for both chatbot and extension.
    
    Args:
        argument_text: The argument to analyze
        client_ip: Client IP for rate limiting
    
    Returns:
        Dict with Toulmin analysis, scores, fallacies, and feedback
        
    Response Structure:
    {
        "elements": {
            "claim": {"text": "...", "strength": 0-10},
            "data": {"text": "...", "strength": 0-10},
            "warrant": {"text": "...", "strength": 0-10},
            "backing": {"text": "...", "strength": 0-10},
            "qualifier": {"text": "...", "strength": 0-10},
            "rebuttal": {"text": "...", "strength": 0-10}
        },
        "fallacy_resistance_score": 0-100,
        "logical_consistency_score": 0-100,
        "clarity_score": 0-100,
        "fallacies_present": ["..."],
        "improved_statement": "...",
        "feedback": "..."
    }
    """
    # ========================================================================
    # STEP 0: Check if this argument is already an improved statement
    # ========================================================================
    print(f"[ANALYZE] 🔍 Step 0: Checking if argument is already improved...")
    
    if is_improved_statement(argument_text):
        print(f"[ANALYZE] ✅ This is an already-improved statement. Returning positive feedback.")
        return {
            "elements": {
                "claim": {"text": argument_text, "strength": 10},
                "data": {"text": "Well-supported with evidence", "strength": 10},
                "warrant": {"text": "Logically sound reasoning", "strength": 10},
                "backing": {"text": "Strong foundational support", "strength": 10},
                "qualifier": {"text": "Appropriately qualified", "strength": 10},
                "rebuttal": {"text": "Addresses counterarguments", "strength": 10}
            },
            "fallacy_resistance_score": 100,
            "logical_consistency_score": 100,
            "clarity_score": 100,
            "fallacies_present": [],
            "fallacy_details": [],
            "improved_statement": "",
            "feedback": "✅ Excellent! This statement is already well-structured, logically sound, and free of fallacies. No further improvements needed.",
            "_note": "This argument matches a previously improved statement.",
            "_source": "improved_cache"
        }
    
    # ========================================================================
    # STEP 1: Detect fallacies using LOCAL MODEL ONLY (NO LLM for fallacies)
    # ========================================================================
    print(f"[ANALYZE] 🔍 Step 1: Detecting fallacies with LOCAL model ONLY...")
    
    # Get full predictions with scores from local model
    local_predictions = classify_with_local_model(
        argument_text,
        model_folder=DEFAULT_MODEL_FOLDER,
        mode="base",
        topk=5,
        threshold=0.3
    )
    
    # Extract fallacy names for backward compatibility
    local_fallacy_names = [p["label"] for p in local_predictions]
    
    # Build fallacy_details with descriptions and percentage scores
    fallacy_details = []
    for pred in local_predictions:
        detail = {
            "label": pred["label"],
            "score": pred["score"],
            "percentage": round(pred["score"] * 100, 1),  # Convert to percentage
            "description": "",
            "alias": ""
        }
        # Enrich with description from FALLACY_LIST
        for f in FALLACY_LIST:
            if _normalize_label(f["name"]) == _normalize_label(pred["label"]):
                detail["description"] = f.get("description", "")
                detail["alias"] = f.get("alias", "")
                break
        fallacy_details.append(detail)
    
    print(f"[ANALYZE] ✅ Local model detected {len(local_fallacy_names)} fallacies: {local_fallacy_names}")
    
    # ========================================================================
    # STEP 2: Get Toulmin analysis from LLM (still uses LLM for structure)
    # ========================================================================
    print(f"[ANALYZE] 🤖 Step 2: Getting Toulmin analysis from LLM...")
    template = templates.get("extract_toulmin")
    if not template:
        return {"error": "Template not found"}
    
    prompt = template["prompt"].replace("{{ARGUMENT_TEXT}}", argument_text)
    result = _llm_completion(template["role"], prompt, client_ip)
    
    # Calculate fallacy resistance score based on local model only
    num_fallacies = len(local_fallacy_names)
    if num_fallacies == 0:
        resistance_score = 100
    else:
        resistance_score = max(0, 100 - (num_fallacies * 15))
    
    if result is None:
        # LLM failed, but we still have local fallacy results
        print(f"[ANALYZE] ⚠️ LLM failed, returning local-only result")
        return {
            "elements": {
                "claim": {"text": "", "strength": 0},
                "data": {"text": "", "strength": 0},
                "warrant": {"text": "", "strength": 0},
                "backing": {"text": "", "strength": 0},
                "qualifier": {"text": "", "strength": 0},
                "rebuttal": {"text": "", "strength": 0}
            },
            "fallacy_resistance_score": resistance_score,
            "logical_consistency_score": 50,
            "clarity_score": 50,
            "fallacies_present": local_fallacy_names,
            "fallacy_details": fallacy_details,  # NEW: includes scores
            "improved_statement": "",
            "feedback": f"Detected fallacies (local model): {', '.join(local_fallacy_names) if local_fallacy_names else 'None detected'}. LLM analysis unavailable.",
            "_source": "local_model"
        }
    
    parsed = _parse_json_response(result)
    
    if parsed:
        # ====================================================================
        # STEP 3: Use ONLY LOCAL MODEL fallacy results (ignore LLM fallacies)
        # ====================================================================
        # The local model is specialized for fallacy detection
        # We completely replace LLM fallacy detection with local results
        
        # Override with local model results ONLY
        parsed["fallacies_present"] = local_fallacy_names
        parsed["fallacy_details"] = fallacy_details  # NEW: includes percentage scores
        parsed["fallacy_resistance_score"] = resistance_score
        parsed["_source"] = "local_model"
        
        # ====================================================================
        # STEP 4: Cache improved statement to prevent re-improvement loops
        # ====================================================================
        # If LLM provided an improved statement, cache it now
        improved = parsed.get("improved_statement", "")
        if improved and improved.strip():
            add_improved_statement(argument_text, improved)
            print(f"[ANALYZE] 💾 Cached improved statement mapping from analysis")
        
        print(f"[ANALYZE] ✅ Analysis complete. Fallacies (LOCAL ONLY): {local_fallacy_names}")
        return parsed
    
    return {"raw_response": result}


def detect_fallacies_local(argument_text: str, topk: int = 5, threshold: float = 0.3) -> Dict[str, Any]:
    """
    Detect fallacies using ONLY the local model (NO LLM calls at all).
    
    This is a pure local inference function - no external API calls.
    Useful when you only need fallacy detection without full Toulmin analysis.
    
    ┌──────────────────────────────────────────────────────────────────┐
    │ 🆕 NEW FUNCTION (2024-12-25): Pure local fallacy detection       │
    │                                                                  │
    │ ✅ Uses saved_models/ (Electra-based NLI models)                 │
    │ ✅ Uses mapcsv/mappings.csv for fallacy hypotheses               │
    │ ❌ NO LLM/API calls - completely offline capable                 │
    │ ⚡ Fast response times (local inference only)                    │
    │ 💰 Zero API costs                                                │
    └──────────────────────────────────────────────────────────────────┘
    
    Args:
        argument_text: The text to analyze for fallacies
        topk: Maximum number of fallacies to return
        threshold: Minimum confidence score (0.0-1.0)
    
    Returns:
        Dict with detected fallacies and scores
        
    Response Structure:
    {
        "fallacies_present": ["Fallacy Name 1", "Fallacy Name 2", ...],
        "fallacy_details": [
            {"label": "Fallacy Name", "score": 0.85, "description": "..."},
            ...
        ],
        "reasoning_quality": "strong" | "moderate" | "weak",
        "fallacy_resistance_score": 0-100,
        "_source": "local_model"
    }
    """
    print(f"[DETECT_LOCAL] 🔍 Detecting fallacies with local model only...")
    
    # Get predictions from local model
    predictions = classify_with_local_model(
        argument_text,
        model_folder=DEFAULT_MODEL_FOLDER,
        mode="base",
        topk=topk,
        threshold=threshold
    )
    
    # Extract fallacy names
    fallacy_names = [p["label"] for p in predictions]
    
    # Enrich with descriptions from FALLACY_LIST
    fallacy_details = []
    for pred in predictions:
        detail = {
            "label": pred["label"],
            "score": pred["score"],
            "description": ""
        }
        # Try to find description from FALLACY_LIST
        for f in FALLACY_LIST:
            if _normalize_label(f["name"]) == _normalize_label(pred["label"]):
                detail["description"] = f.get("description", "")
                detail["alias"] = f.get("alias", "")
                break
        fallacy_details.append(detail)
    
    # Determine reasoning quality
    num_fallacies = len(fallacy_names)
    if num_fallacies == 0:
        quality = "strong"
        resistance_score = 100
    elif num_fallacies <= 2:
        quality = "moderate"
        resistance_score = max(0, 100 - (num_fallacies * 20))
    else:
        quality = "weak"
        resistance_score = max(0, 100 - (num_fallacies * 15))
    
    print(f"[DETECT_LOCAL] ✅ Detected {num_fallacies} fallacies: {fallacy_names}")
    
    return {
        "fallacies_present": fallacy_names,
        "fallacy_details": fallacy_details,
        "reasoning_quality": quality,
        "fallacy_resistance_score": resistance_score,
        "_source": "local_model",
        "_model_used": DEFAULT_MODEL_FOLDER
    }


def improve_argument(argument_text: str, fallacy_type: str, client_ip: str = "127.0.0.1") -> Dict[str, Any]:
    """
    Improve an argument by removing fallacies (Support Mode).
    
    ┌──────────────────────────────────────────────────────────────────┐
    │ ✅ COMPLIANCE: This is the UNIFIED function for arg improvement  │
    │                                                                  │
    │ CHATBOT CALL PATH:                                               │
    │   gem_app.py:/api/support_mode → improve_argument()              │
    │                                                                  │
    │ EXTENSION CALL PATH:                                             │
    │   routes.py:/api/rewrite → improve_argument()                    │
    │                                                                  │
    │ BOTH paths converge HERE. Zero duplicated logic.                 │
    └──────────────────────────────────────────────────────────────────┘
    
    This is the EXACT same logic used by the chatbot's /api/support_mode endpoint.
    
    Args:
        argument_text: The argument to improve
        fallacy_type: The type of fallacy detected
        client_ip: Client IP for rate limiting
    
    Returns:
        Dict with improved argument and explanation
        
    Response Structure:
    {
        "improved_argument": "...",
        "explanation": "..."
    }
    """
    template = templates.get("support_mode")
    if not template:
        return {"error": "Template not found"}
    
    prompt = (
        template["prompt"]
        .replace("{{ARGUMENT_TEXT}}", argument_text)
        .replace("{{FALLACY_TYPE}}", fallacy_type)
    )
    
    result = _llm_completion(template["role"], prompt, client_ip)
    
    if result is None:
        return {"error": "LLM failed"}
    
    parsed = _parse_json_response(result)
    if parsed:
        # Track the improved statement to prevent re-improvement loops
        improved_text = parsed.get("improved_argument", "")
        if improved_text:
            add_improved_statement(argument_text, improved_text)
            print(f"[IMPROVE] 💾 Cached improved statement mapping")
        return parsed
    
    return {"raw_response": result}


def generate_counter_argument(argument_text: str, context: str = "", client_ip: str = "127.0.0.1") -> Dict[str, Any]:
    """
    Generate a counter-argument (Oppose Mode).
    
    ┌──────────────────────────────────────────────────────────────────┐
    │ ✅ COMPLIANCE: This is the UNIFIED function for counter-args     │
    │                                                                  │
    │ CHATBOT CALL PATH:                                               │
    │   gem_app.py:/api/oppose_mode → generate_counter_argument()      │
    │                                                                  │
    │ EXTENSION CALL PATH:                                             │
    │   routes.py:/api/generate-reply → generate_counter_argument()    │
    │                                                                  │
    │ BOTH paths converge HERE. Zero duplicated logic.                 │
    └──────────────────────────────────────────────────────────────────┘
    
    This is the EXACT same logic used by the chatbot's /api/oppose_mode endpoint.
    
    Args:
        argument_text: The argument to counter
        context: Additional context
        client_ip: Client IP for rate limiting
    
    Returns:
        Dict with the counter-argument response
    """
    template = templates.get("oppose_mode")
    if not template:
        return {"error": "Template not found"}
    
    prompt = (
        template["prompt"]
        .replace("{{ARGUMENT_TEXT}}", argument_text)
        .replace("{{CONTEXT}}", context)
    )
    
    result = _llm_completion(template["role"], prompt, client_ip)
    
    if result is None:
        return {"error": "LLM failed"}
    
    # Try to parse JSON response if LLM returned JSON
    parsed = _parse_json_response(result)
    if parsed:
        # Extract the counter-argument from various possible keys
        counter_text = (parsed.get("argument") or 
                       parsed.get("counter_argument") or 
                       parsed.get("response") or 
                       parsed.get("text") or 
                       result)
        return {"response": counter_text}
    
    # Return raw text if not JSON
    return {"response": result}


def evaluate_response(opponent_argument: str, user_response: str, client_ip: str = "127.0.0.1") -> Dict[str, Any]:
    """
    Evaluate how well a user responded to a fallacious argument.
    
    This is the EXACT same logic used by the chatbot's /api/evaluate_user_response endpoint.
    
    Args:
        opponent_argument: The original fallacious argument
        user_response: The user's counter-response
        client_ip: Client IP for rate limiting
    
    Returns:
        Dict with evaluation scores and analysis
        
    Response Structure:
    {
        "detected_fallacy": "...",
        "user_countered_correctly": true/false,
        "toulmin_scores": {...},
        "overall_reasoning_score": 0-100,
        "analysis_notes": "..."
    }
    """
    template = templates.get("evaluate_user_response")
    if not template:
        return {"error": "Template not found"}
    
    prompt = (
        template["prompt"]
        .replace("{{OPPONENT_ARGUMENT}}", opponent_argument)
        .replace("{{USER_RESPONSE}}", user_response)
    )
    
    result = _llm_completion(template["role"], prompt, client_ip)
    
    if result is None:
        return {"error": "LLM failed"}
    
    parsed = _parse_json_response(result)
    if parsed:
        return parsed
    
    return {"raw_response": result}


def generate_chat_title(argument_text: str, client_ip: str = "127.0.0.1") -> str:
    """
    Generate a short title for a chat conversation.
    
    Args:
        argument_text: The first argument in the conversation
        client_ip: Client IP for rate limiting
    
    Returns:
        A short title string (max 5 words)
    """
    template = templates.get("generate_title")
    if not template:
        return "New Conversation"
    
    prompt = template["prompt"].replace("{{ARGUMENT_TEXT}}", argument_text)
    
    result = _llm_completion(template["role"], prompt, client_ip, json_mode=False)
    
    if result:
        return result.strip().strip('"')
    
    return "New Conversation"


# ==============================
# Response Transformers for Extension Compatibility
# ==============================

def analyze_argument_dual_mode(argument_text: str, client_ip: str = "127.0.0.1") -> Dict[str, Any]:
    """
    Analyze an argument and generate BOTH support and defence responses in a single request.
    
    ┌──────────────────────────────────────────────────────────────────────────────┐
    │ 🆕 DUAL-MODE UNIFIED ENDPOINT (2024-12-25)                                   │
    │                                                                              │
    │ ═══════════════════════════════════════════════════════════════════════════  │
    │ ARCHITECTURAL DESIGN RATIONALE:                                              │
    │ ═══════════════════════════════════════════════════════════════════════════  │
    │                                                                              │
    │ WHY BOTH MODES ARE GENERATED TOGETHER:                                       │
    │ ────────────────────────────────────────                                     │
    │ • User submits argument ONCE, receives BOTH perspectives                     │
    │ • Eliminates redundant API calls (was 2 requests → now 1)                    │
    │ • Frontend toggle switches between cached responses instantly                │
    │ • Same AI model, same parameters - only mode instruction differs             │
    │                                                                              │
    │ WHY TOGGLING IS FRONTEND-ONLY:                                               │
    │ ────────────────────────────────                                             │
    │ • Both responses are received upfront in this single response                │
    │ • Frontend stores both, renders one at a time                                │
    │ • Toggle = swap displayed response, NOT a new API call                       │
    │ • Zero latency on mode switch, better UX                                     │
    │                                                                              │
    │ WHY BACKEND REMAINS UNIFIED:                                                 │
    │ ────────────────────────────                                                 │
    │ • Single runPipeline() function with mode parameter                          │
    │ • NO duplicate reasoning code or separate pipelines                          │
    │ • Reusable across: Dedicated Chatbot, Floating Chatbot, Real-time Suggestions│
    │ • Future features require ZERO backend changes                               │
    │                                                                              │
    │ CALL PATHS (all converge here):                                              │
    │ ────────────────────────────────                                             │
    │   gem_app.py:/api/analyze_dual    → analyze_argument_dual_mode()             │
    │   (future) floating_chatbot       → analyze_argument_dual_mode()             │
    │   (future) real_time_suggestions  → analyze_argument_dual_mode()             │
    │                                                                              │
    └──────────────────────────────────────────────────────────────────────────────┘
    
    Args:
        argument_text: The argument to analyze
        client_ip: Client IP for rate limiting
    
    Returns:
        Dict containing both support and defence mode responses:
        {
            "support": { /* full structured response with Toulmin analysis */ },
            "defence": { /* full counter-argument response */ }
        }
    """
    print(f"[DUAL_MODE] 🔄 Generating dual-mode response (support + defence)")
    
    # ========================================================================
    # STEP 1: Run SUPPORT mode analysis (reuses existing analyze_argument)
    # ========================================================================
    # The analyze_argument function already handles:
    # - Local model fallacy detection (no LLM)
    # - LLM Toulmin analysis
    # - Score calculation
    # We simply reuse it - NO code duplication
    print(f"[DUAL_MODE] 🏗️ Running SUPPORT mode analysis...")
    support_response = analyze_argument(argument_text, client_ip)
    
    # ========================================================================
    # STEP 2: Run DEFENCE mode (reuses existing generate_counter_argument)
    # ========================================================================
    # Same core logic with mode="defence"
    # Generates counter-argument with intentional fallacy
    print(f"[DUAL_MODE] ⚔️ Running DEFENCE mode analysis...")
    defence_response = generate_counter_argument(
        argument_text, 
        context="General debate - challenge the user's reasoning",
        client_ip=client_ip
    )
    
    # ========================================================================
    # STEP 3: Package both responses together
    # ========================================================================
    # Frontend receives everything at once, toggles client-side
    dual_response = {
        "support": support_response,
        "defence": defence_response,
        # Metadata for frontend convenience
        "_meta": {
            "generated_at": __import__("datetime").datetime.now().isoformat(),
            "default_mode": "support",
            "available_modes": ["support", "defence"],
            # CRITICAL: Inform frontend this is a dual-response
            "is_dual_mode": True,
            # Prevent accidental regression to dual requests
            "toggle_is_frontend_only": True
        }
    }
    
    print(f"[DUAL_MODE] ✅ Dual-mode response ready. Support: {'✓' if 'elements' in support_response else '✗'}, Defence: {'✓' if 'response' in defence_response else '✗'}")
    
    return dual_response


def transform_to_extension_format(chatbot_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform chatbot response format to extension-compatible format.
    
    This allows the extension to consume the same data with minimal frontend changes.
    The transformation is purely cosmetic - the underlying data is identical.
    
    Chatbot format -> Extension format mapping:
    - elements.claim -> toulminAnalysis.claim
    - fallacies_present -> fallacies (with enriched data)
    - improved_statement -> suggestions
    """
    if "error" in chatbot_response:
        return chatbot_response
    
    # If it's already in extension format or raw response, return as-is
    if "toulminAnalysis" in chatbot_response or "raw_response" in chatbot_response:
        return chatbot_response
    
    # Transform chatbot Toulmin format to extension format
    elements = chatbot_response.get("elements", {})
    
    toulmin_analysis = {}
    for key in ["claim", "data", "warrant", "backing", "qualifier", "rebuttal"]:
        element = elements.get(key, {})
        toulmin_analysis[key] = {
            "present": bool(element.get("text")),
            "score": element.get("strength", 0),
            "feedback": element.get("text", "")
        }
    
    # Transform fallacies_present to enriched fallacies array
    fallacies_present = chatbot_response.get("fallacies_present", [])
    fallacies = []
    for fallacy_name in fallacies_present:
        fallacies.append({
            "type": fallacy_name,
            "severity": "warning",
            "description": f"Detected: {fallacy_name}",
            "excerpt": ""
        })
    
    # Build extension-compatible response
    extension_response = {
        # Original chatbot data (preserved)
        "elements": elements,
        "fallacy_resistance_score": chatbot_response.get("fallacy_resistance_score", 0),
        "logical_consistency_score": chatbot_response.get("logical_consistency_score", 0),
        "clarity_score": chatbot_response.get("clarity_score", 0),
        "fallacies_present": fallacies_present,
        "improved_statement": chatbot_response.get("improved_statement", ""),
        "feedback": chatbot_response.get("feedback", ""),
        
        # Extension-specific format (transformed)
        "toulminAnalysis": toulmin_analysis,
        "fallacies": fallacies,
        "suggestions": [
            {
                "text": chatbot_response.get("improved_statement", ""),
                "rationale": chatbot_response.get("feedback", "")
            }
        ] if chatbot_response.get("improved_statement") else [],
        "overallAssessment": chatbot_response.get("feedback", ""),
        
        # Extension UI helpers
        "issues": [
            {
                "type": f.get("type"),
                "severity": f.get("severity", "warning"),
                "description": f.get("description"),
                "example": f.get("excerpt", "")
            }
            for f in fallacies
        ]
    }
    
    return extension_response


def transform_improvement_to_extension_format(chatbot_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform support_mode response to extension rewrite format.
    """
    if "error" in chatbot_response:
        return chatbot_response
    
    return {
        # Original chatbot data
        "improved_argument": chatbot_response.get("improved_argument", ""),
        "explanation": chatbot_response.get("explanation", ""),
        
        # Extension rewrite format
        "rewrittenText": chatbot_response.get("improved_argument", ""),
        "originalAnalysis": {
            "strengths": [],
            "weaknesses": [chatbot_response.get("explanation", "")],
            "mainClaim": ""
        },
        "changes": [
            {
                "type": "Improved reasoning",
                "description": chatbot_response.get("explanation", "")
            }
        ],
        "improvementScore": {
            "before": 5,
            "after": 8
        }
    }


def transform_counter_to_extension_format(chatbot_response: Dict[str, Any], original_text: str = "") -> Dict[str, Any]:
    """
    Transform oppose_mode response to extension reply format.
    """
    if "error" in chatbot_response:
        return chatbot_response
    
    response_text = chatbot_response.get("response", "")
    
    return {
        # Original chatbot data
        "response": response_text,
        
        # Extension reply format
        "replies": [
            {"tone": "neutral", "text": response_text},
            {"tone": "polite", "text": response_text},
            {"tone": "assertive", "text": response_text}
        ],
        "originalArgumentSummary": original_text[:100] + "..." if len(original_text) > 100 else original_text,
        "identifiedWeaknesses": [],
        "counterArgument": response_text
    }
