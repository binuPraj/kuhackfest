from flask import Flask, request, jsonify
from flask_cors import CORS             #allows frontend to call thus api from another origin
import json
import os
from dotenv import load_dotenv
from pathlib import Path
import requests
import torch
import pandas as pd
from transformers import AutoConfig, AutoTokenizer, AutoModelForSequenceClassification
import re

# ==============================
# Load environment variables
# ==============================
# Print current working directory
print(f"[DEBUG] Current working directory: {os.getcwd()}")

# Load .env from the backend directory explicitly
env_path = Path(__file__).parent / '.env'
print(f"[DEBUG] Looking for .env at: {env_path}")
print(f"[DEBUG] .env file exists: {env_path.exists()}")

load_dotenv(dotenv_path=env_path)

app = Flask(__name__)               #flask server created
CORS(app)                           #enable CORS so frontend cna acceess /api/*

# ==============================
# OpenRouter Configuration
# ==============================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
# List of free models to try in order of preference
FREE_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "qwen/qwen-2-7b-instruct:free",
    "google/gemma-3-27b-it:free",
]
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
USE_LLM = os.getenv("USE_LLM", "1") == "1"  # set USE_LLM=0 in .env to disable external calls

# Track rate limit status and last error globally
_RATE_LIMITED = False
_RATE_LIMIT_MSG = ""
_LAST_LLM_ERROR = ""

if OPENROUTER_API_KEY:
    print(f"[DEBUG] OPENROUTER_API_KEY loaded: {OPENROUTER_API_KEY[:20]}...")
    print(f"[DEBUG] Full API key length: {len(OPENROUTER_API_KEY)}")
else:
    print("[ERROR] OPENROUTER_API_KEY not found!")
    print(f"[DEBUG] Available env vars: {list(os.environ.keys())[:10]}")

if not OPENROUTER_API_KEY and USE_LLM:
    print("[ERROR] FATAL: OPENROUTER_API_KEY is not set. Check your .env file.")

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "http://localhost:5000",
    "X-Title": "Argument Analysis API"
}                                                       # headers that authenticate our request
                                                        # backend sends requests to oprnrouter, openrouter runs gemma3 and returns result

# ==============================
# Load Prompt Templates & Fallacy List
# ==============================
TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), "templates.json")
DB_PATH = os.path.join(os.path.dirname(__file__), "../public/data/db.json")
FALLACIES_JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "public", "data", "logicalfallacy.json")

try:
    with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
        templates = json.load(f)
except FileNotFoundError:
    print("[ERROR] templates.json not found")
    templates = {}

def load_fallacy_list():
    """Load the 13 fallacies from logicalfallacy.json"""
    try:
        with open(FALLACIES_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)                 #parse json into python i.e.e json file into a dictionary
            fallacies = []
            for f_item in data.get("fallacies", []):
                fallacies.append({
                    "name": f_item["name"],
                    "alias": f_item.get("alias", ""),
                    "description": f_item["description"]
                })
            print(f"[SUCCESS] Loaded {len(fallacies)} fallacies from logicalfallacy.json")
            return fallacies
    except Exception as e:
        print(f"[ERROR] Error loading fallacies JSON: {e}")
        return []

FALLACY_LIST = load_fallacy_list()


def _normalize_label(name: str) -> str:
    """Normalize fallacy/label names for robust matching.
    Removes parenthetical phrases, punctuation, and normalizes whitespace/lowercase.
    """
    if not name:
        return ""
    # remove parenthetical content like 'Ad Hominem (Personal Attack)'
    name = re.sub(r"\(.*?\)", "", name)
    # lowercase and strip punctuation (keep alphanumerics and spaces)
    name = re.sub(r"[^a-z0-9\s]", "", name.lower())
    # collapse whitespace
    name = " ".join(name.split())
    return name

# Ensure DB directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)



# ==============================
# Helper: Recalculate Global Insights
# ==============================
def recalculate_insights(db_data):
    """
    Recalculate aggregate insights from all arguments across all chats.
    Updates the 'insights' object in db_data with averages.
    """
    # Initialize accumulators
    total_fallacy_resistance = 0
    total_logical_consistency = 0
    total_clarity = 0
    radar_totals = {"claim": 0, "data": 0, "warrant": 0, "backing": 0, "qualifier": 0, "rebuttal": 0}
    fallacy_counts = {}  # Track fallacy occurrences
    support_mode_count = 0  # Only count support mode responses (they have the metrics)
    
    for chat in db_data.get("chats", []):
        for arg in chat.get("arguments", []):
            # Only process support mode responses (they have Toulmin analysis)
            if arg.get("mode_used") != "support":
                continue
                
            response = arg.get("response", {})
            if not response or not isinstance(response, dict):
                continue
            
            # Skip if no elements (not a proper Toulmin response)
            if "elements" not in response:
                continue
                
            support_mode_count += 1
            
            # Accumulate scores (these are 0-100 scale)
            total_fallacy_resistance += response.get("fallacy_resistance_score", 0)
            total_logical_consistency += response.get("logical_consistency_score", 0)
            total_clarity += response.get("clarity_score", 0)
            
            # Accumulate radar metrics (element strengths are 0-10 scale)
            elements = response.get("elements", {})
            for key in radar_totals:
                element = elements.get(key, {})
                if isinstance(element, dict):
                    radar_totals[key] += element.get("strength", 0)
            
            # Count fallacies
            for fallacy in response.get("fallacies_present", []):
                fallacy_counts[fallacy] = fallacy_counts.get(fallacy, 0) + 1
    
    # Calculate averages
    if support_mode_count > 0:
        avg_fallacy_resistance = round(total_fallacy_resistance / support_mode_count, 1)
        avg_logical_consistency = round(total_logical_consistency / support_mode_count, 1)
        avg_clarity = round(total_clarity / support_mode_count, 1)
        # Radar metrics: average of 0-10 scores
        avg_radar = {k: round(v / support_mode_count, 1) for k, v in radar_totals.items()}
    else:
        avg_fallacy_resistance = 0
        avg_logical_consistency = 0
        avg_clarity = 0
        avg_radar = {k: 0 for k in radar_totals}
    
    # Get top 5 most common fallacies
    sorted_fallacies = sorted(fallacy_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    common_fallacies = [{"type": f[0], "count": f[1]} for f in sorted_fallacies]
    
    # Update db_data insights
    db_data["insights"] = {
        "radar_metrics": avg_radar,
        "fallacy_resistance_score": avg_fallacy_resistance,
        "logical_consistency_score": avg_logical_consistency,
        "clarity_score": avg_clarity,
        "common_fallacies_faced": common_fallacies,
        "total_arguments_analyzed": support_mode_count
    }
    
    return db_data

# ==============================
# Helper Functions
# ==============================
def clean_json_response(response_text):
    """
    Cleans the LLM response to ensure it's valid JSON.
    Removes markdown code blocks and whitespace.
    """
    if not response_text:
        return None
    
    cleaned = response_text.strip()
    
    # Remove markdown code blocks if present
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
        
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
        
    return cleaned.strip()

#llm donot return clean json even when asked to, so this function cleans the response. without this our api might crash frequently

# ==============================
# OpenRouter LLM Call
# ==============================

# builds llm req, sends it to openrouter, vlaidates response structure, extracts text output, cleans it, returns Json-safe string
def llm_completion(system_role, prompt, json_mode=True):
    """
    Call OpenRouter with multiple model fallbacks. If json_mode=True the user content will be forced to return JSON.
    """
    global _RATE_LIMITED, _RATE_LIMIT_MSG, _LAST_LLM_ERROR
    
    print("\n[LLM_DEBUG] ===== llm_completion called =====")
    print(f"[LLM_DEBUG] json_mode: {json_mode}")
    print(f"[LLM_DEBUG] system_role length: {len(system_role)}")
    print(f"[LLM_DEBUG] prompt length: {len(prompt)}")
    print(f"[LLM_DEBUG] API key present: {bool(OPENROUTER_API_KEY)}")
    print(f"[LLM_DEBUG] API key: {OPENROUTER_API_KEY[:20]}...{OPENROUTER_API_KEY[-10:] if OPENROUTER_API_KEY else 'None'}")
    
    # Guard: skip LLM if disabled or missing key
    if not USE_LLM:
        _LAST_LLM_ERROR = "USE_LLM=0, LLM calls disabled"
        print(f"[LLM_DEBUG] {_LAST_LLM_ERROR}")
        return None
    if not OPENROUTER_API_KEY:
        _LAST_LLM_ERROR = "No OPENROUTER_API_KEY set in .env"
        print(f"[LLM_DEBUG] {_LAST_LLM_ERROR}")
        return None

    user_content = prompt
    if json_mode:
        user_content = prompt + "\n\nReturn ONLY valid JSON. No explanation. No markdown."

    # Try each model until one works
    for model in FREE_MODELS:
        print(f"\n[LLM_DEBUG] Trying model: {model}")
        
        # Build fresh headers with current API key
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5000",
            "X-Title": "Cognix Fallacy Detector"
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_role},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.0,
            "max_tokens": 2048
        }

        try:
            print(f"[LLM_DEBUG] Making POST request to {model}...")
            response = requests.post(
                OPENROUTER_URL,
                headers=headers,
                json=payload,
                timeout=60
            )
            
            print(f"[LLM_DEBUG] Response status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                if "choices" in data and data["choices"]:
                    content = data["choices"][0]["message"]["content"]
                    print(f"[LLM_DEBUG] ✅ Success with {model}!")
                    print(f"[LLM_DEBUG] Content preview: {content[:200]}...")
                    _RATE_LIMITED = False
                    _LAST_LLM_ERROR = ""
                    cleaned = clean_json_response(content)
                    return cleaned
                else:
                    _LAST_LLM_ERROR = f"No choices in response from {model}"
                    print(f"[ERROR] {_LAST_LLM_ERROR}: {data}")
                    continue
            
            # Handle errors
            try:
                err_data = response.json()
                err_msg = err_data.get("error", {}).get("message", str(err_data))
            except:
                err_msg = response.text[:200]
            
            if response.status_code == 429:
                _RATE_LIMITED = True
                _RATE_LIMIT_MSG = err_msg
                _LAST_LLM_ERROR = f"Rate limit on {model}: {err_msg}"
                print(f"[WARN] {_LAST_LLM_ERROR}")
                continue  # Try next model
            else:
                _LAST_LLM_ERROR = f"Error {response.status_code} on {model}: {err_msg}"
                print(f"[ERROR] {_LAST_LLM_ERROR}")
                continue  # Try next model

        except requests.exceptions.Timeout:
            _LAST_LLM_ERROR = f"Timeout on {model}"
            print(f"[ERROR] {_LAST_LLM_ERROR}")
            continue
        except Exception as e:
            _LAST_LLM_ERROR = f"Exception on {model}: {str(e)}"
            print(f"[ERROR] {_LAST_LLM_ERROR}")
            import traceback
            traceback.print_exc()
            continue

    # All models failed
    _LAST_LLM_ERROR = f"All {len(FREE_MODELS)} models failed. Last error: {_LAST_LLM_ERROR}"
    print(f"[ERROR] {_LAST_LLM_ERROR}")
    return None

# ------------------------------
# Local model classification helpers (adapted from quick_test.py)
# ------------------------------
_LOCAL_MODEL_CACHE = {}

def _fallback_tokenizer_id(model_type):
    if model_type == "electra":
        return "google/electra-base-discriminator"
    if model_type == "deberta":
        return "microsoft/deberta-base"
    if model_type == "roberta":
        return "roberta-base"
    if model_type == "bert":
        return "bert-base-uncased"
    return "bert-base-uncased"


def load_tokenizer(model_path, explicit_tokenizer=None):
    if explicit_tokenizer:
        try:
            return AutoTokenizer.from_pretrained(explicit_tokenizer)
        except Exception as e:
            print(f"[WARN] Failed loading tokenizer '{explicit_tokenizer}': {e}")

    try:
        return AutoTokenizer.from_pretrained(model_path)
    except Exception:
        pass

    try:
        cfg = AutoConfig.from_pretrained(model_path)
        fallback_id = _fallback_tokenizer_id(getattr(cfg, "model_type", ""))
        print(f"[INFO] Using fallback tokenizer: {fallback_id}")
        return AutoTokenizer.from_pretrained(fallback_id)
    except Exception as e:
        print(f"[ERROR] Loading fallback tokenizer failed: {e}")
        raise


def build_hypothesis(label, mdf, mode):
    if mode == "base":
        return f"This is an example of {label} logical fallacy"

    if mode == "simplify":
        name = mdf.loc[mdf["Original Name"] == label, "Understandable Name"].values[0]
        return f"This is an example of {name}"

    if mode == "description":
        desc = mdf.loc[mdf["Original Name"] == label, "Description"].values[0]
        return f"This is an example of {desc}"

    if mode == "logical-form":
        form = mdf.loc[mdf["Original Name"] == label, "Logical Form"].values[0]
        return f"This article matches the following logical form: {form}"

    if mode == "masked-logical-form":
        form = mdf.loc[mdf["Original Name"] == label, "Masked Logical Form"].values[0]
        return f"This article matches the following logical form: {form}"

    return f"This is an example of {label} logical fallacy"


def classify_with_local_model(argument_text, model_folder, mappings_csv=None, mode="base", topk=5):
    """
    Returns topk predictions from local saved model folder.
    `model_folder` is a path relative to this file or an absolute path.
    """
    # Resolve model path
    base_dir = os.path.join(os.path.dirname(__file__), "../saved_models")
    model_path = model_folder
    if not os.path.isabs(model_path):
        model_path = os.path.normpath(os.path.join(base_dir, model_folder))

    print(f"[DEBUG] Model path resolved to: {model_path}")
    print(f"[DEBUG] Model path exists: {os.path.exists(model_path)}")

    cache_key = f"{model_path}|{mappings_csv}|{mode}"
    device = "cuda" if torch.cuda.is_available() else "cpu"

    if cache_key not in _LOCAL_MODEL_CACHE:
        # load mapping
        csv_path = mappings_csv or os.path.join(os.path.dirname(__file__), "../mapcsv/mappings.csv")
        print(f"[DEBUG] CSV path: {csv_path}")
        try:
            mappings_df = pd.read_csv(csv_path)
            print(f"[DEBUG] Loaded {len(mappings_df)} fallacy labels")
        except Exception as e:
            print(f"[WARN] Failed loading mappings csv {csv_path}: {e}")
            mappings_df = pd.DataFrame({"Original Name": []})

        try:
            tokenizer = load_tokenizer(model_path)
            print(f"[DEBUG] Tokenizer loaded successfully")
        except Exception as e:
            print(f"[WARN] Tokenizer load failed, trying fallback: {e}")
            tokenizer = AutoTokenizer.from_pretrained("google/electra-base-discriminator")
            print(f"[DEBUG] Fallback tokenizer loaded")

        try:
            model = AutoModelForSequenceClassification.from_pretrained(model_path)
            model.to(device)
            model.eval()
        except Exception as e:
            print(f"[ERROR] Loading model failed: {e}")
            # Fallback to a local MNLI model if available
            fallback_dir = os.path.normpath(os.path.join(base_dir, "electra-base-mnli"))
            if os.path.exists(fallback_dir):
                print(f"[INFO] Falling back to local MNLI model: {fallback_dir}")
                tokenizer = AutoTokenizer.from_pretrained(fallback_dir)
                model = AutoModelForSequenceClassification.from_pretrained(fallback_dir)
                model.to(device)
                model.eval()
            else:
                print("[ERROR] No local fallback model available. Returning empty predictions.")
                # Cache a minimal stub to avoid repeated failures
                _LOCAL_MODEL_CACHE[cache_key] = {
                    "model": None,
                    "tokenizer": tokenizer,
                    "mappings_df": mappings_df,
                    "device": device
                }
                return []

        _LOCAL_MODEL_CACHE[cache_key] = {
            "model": model,
            "tokenizer": tokenizer,
            "mappings_df": mappings_df,
            "device": device
        }

    info = _LOCAL_MODEL_CACHE[cache_key]
    model = info["model"]
    tokenizer = info["tokenizer"]
    mappings_df = info["mappings_df"]
    device = info["device"]

    labels = list(mappings_df.get("Original Name", []))

    # Keep only the canonical 13 fallacies loaded from logicalfallacy.json,
    # using normalized matching to handle variations like parentheticals.
    try:
        canonical_map = { _normalize_label(f["name"]): f["name"] for f in FALLACY_LIST }
        filtered = []
        for l in labels:
            norm = _normalize_label(l)
            if norm in canonical_map:
                filtered.append(canonical_map[norm])
        labels = filtered
    except Exception:
        # If FALLACY_LIST isn't available or malformed, fall back to original labels
        pass

    if len(labels) == 0:
        return []

    hypotheses = [build_hypothesis(lbl, mappings_df, mode) for lbl in labels]

    batch = tokenizer(
        [argument_text] * len(labels),
        hypotheses,
        padding=True,
        truncation=True,
        return_tensors="pt"
    )

    batch = {k: v.to(device) for k, v in batch.items()}

    # If no model loaded, return empty
    if model is None:
        return []

    with torch.no_grad():
        logits = model(**batch).logits
        # For MNLI-style models, the "entailment" index is often 2 (bart-large-mnli),
        # but Electra MNLI can have label mapping different. We default to the first column
        # to keep behavior consistent with previous code. Adjust if needed.
        probs = torch.softmax(logits, dim=1)[:, 0]

    scores = list(zip(labels, probs.cpu().tolist()))
    scores.sort(key=lambda x: x[1], reverse=True)

    return [{"label": lbl, "score": float(score)} for lbl, score in scores[:topk]]

# ------------------------------
# New endpoint: classify_fallacy (LLM + local)
# ------------------------------

def generate_chat_title(argument_text):
    template = templates.get("generate_title")
    if not template:
        return "New Conversation"
        
    prompt = template["prompt"].replace("{{ARGUMENT_TEXT}}", argument_text)
    
    # We don't need JSON for the title, just the text
    # But llm_completion enforces JSON in the prompt usually.
    # Let's make a simpler call or just use llm_completion and expect a string if we change the prompt in templates.json
    # The template I added says "Return ONLY valid JSON" in the system prompt? No, I didn't add that to the template.
    # But llm_completion adds "\n\nReturn ONLY valid JSON..." to the prompt.
    # I should probably make llm_completion more flexible or just handle the string return.
    
    # Actually, let's just use a separate call logic or modify llm_completion to take an optional "json_mode" param.
    # For now, to minimize changes, I'll just use llm_completion but I need to be careful about the "Return ONLY valid JSON" suffix.
    # I'll modify llm_completion to accept an optional suffix override.
    
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": template["role"]},
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.7
    }
    
    try:
        response = requests.post(
            OPENROUTER_URL,
            headers=HEADERS,
            data=json.dumps(payload),
            timeout=60
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip().strip('"')
    except:
        pass
        
    return "New Conversation"

# ==============================
# API ROUTES
# ==============================
@app.route("/api/extract_toulmin", methods=["POST"])
def extract_toulmin():
    try:
        print("\n\n[DEBUG] ===== extract_toulmin endpoint called =====")
        data = request.get_json(force=True)
        print(f"[DEBUG] Request data keys: {list(data.keys())}")
        
        argument_text = data.get("argument_text")
        print(f"[DEBUG] argument_text length: {len(argument_text) if argument_text else 0}")
        print(f"[DEBUG] argument_text: {argument_text[:100] if argument_text else 'None'}...")

        if not argument_text:
            print("[ERROR] No argument_text in request")
            return jsonify({"error": "Missing argument_text"}), 400

        print("[DEBUG] Loading template...")
        template = templates.get("extract_toulmin")
        if not template:
            print("[ERROR] Template 'extract_toulmin' not found")
            print(f"[ERROR] Available templates: {list(templates.keys())}")
            return jsonify({"error": "Template not found"}), 500

        print(f"[DEBUG] Template role: {template.get('role', 'N/A')[:50]}")
        print(f"[DEBUG] Template prompt length: {len(template.get('prompt', ''))}")
        
        print("[DEBUG] Building prompt...")
        prompt = template["prompt"].replace("{{ARGUMENT_TEXT}}", argument_text)
        print(f"[DEBUG] Prompt first 200 chars: {prompt[:200]}...")

        print("[DEBUG] Calling llm_completion...")
        result = llm_completion(template["role"], prompt)
        
        print(f"[DEBUG] LLM returned: {type(result)}")
        print(f"[DEBUG] Result is None: {result is None}")
        
        if result is None:
            print("[ERROR] llm_completion returned None")
            if _RATE_LIMITED:
                return jsonify({
                    "error": "Rate limit exceeded", 
                    "message": _RATE_LIMIT_MSG or "OpenRouter free tier limit reached. Resets at midnight UTC.",
                    "rate_limited": True
                }), 429
            return jsonify({"error": "LLM failed - check API key or try again"}), 500

        print(f"[DEBUG] Result length: {len(result)}")
        print(f"[DEBUG] Result first 300 chars: {result[:300]}...")
        
        print("[DEBUG] Parsing JSON...")
        parsed = json.loads(result)
        print(f"[DEBUG] Successfully parsed JSON with keys: {list(parsed.keys())}")
        return jsonify(parsed)
        
    except json.JSONDecodeError as e:
        print(f"[JSON ERROR] {e}")
        print(f"[JSON ERROR] Raw result: {result if 'result' in locals() else 'N/A'}")
        return jsonify({"error": "Invalid JSON from LLM"}), 500
    except Exception as e:
        print(f"\n\n[FATAL ERROR in extract_toulmin]: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
        return jsonify({"raw_response": result})

@app.route("/api/support_mode", methods=["POST"])
def support_mode():
    data = request.get_json(force=True)
    argument_text = data.get("argument_text")
    fallacy_type = data.get("fallacy_type")

    if not argument_text or not fallacy_type:
        return jsonify({"error": "Missing argument_text or fallacy_type"}), 400

    template = templates.get("support_mode")
    if not template:
        return jsonify({"error": "Template not found"}), 500

    prompt = (
        template["prompt"]
        .replace("{{ARGUMENT_TEXT}}", argument_text)
        .replace("{{FALLACY_TYPE}}", fallacy_type)
    )

    result = llm_completion(template["role"], prompt)
    if result is None:
        if _RATE_LIMITED:
            return jsonify({
                "error": "Rate limit exceeded", 
                "message": _RATE_LIMIT_MSG or "OpenRouter free tier limit reached. Resets at midnight UTC.",
                "debug": _LAST_LLM_ERROR,
                "rate_limited": True
            }), 429
        return jsonify({
            "error": "LLM failed", 
            "message": _LAST_LLM_ERROR or "All models failed - check console for details",
            "debug": _LAST_LLM_ERROR
        }), 500

    try:
        return jsonify(json.loads(result))
    except json.JSONDecodeError:
        return jsonify({"raw_response": result})

@app.route("/api/oppose_mode", methods=["POST"])
def oppose_mode():
    data = request.get_json(force=True)
    argument_text = data.get("argument_text")
    context = data.get("context", "")

    if not argument_text:
        return jsonify({"error": "Missing argument_text"}), 400

    template = templates.get("oppose_mode")
    if not template:
        return jsonify({"error": "Template not found"}), 500

    prompt = (
        template["prompt"]
        .replace("{{ARGUMENT_TEXT}}", argument_text)
        .replace("{{CONTEXT}}", context)
    )

    result = llm_completion(template["role"], prompt)
    if result is None:
        if _RATE_LIMITED:
            return jsonify({
                "error": "Rate limit exceeded", 
                "message": _RATE_LIMIT_MSG or "OpenRouter free tier limit reached. Resets at midnight UTC.",
                "rate_limited": True
            }), 429
        return jsonify({"error": "LLM failed - check API key or try again"}), 500

    return jsonify({"response": result})


@app.route("/api/classify_fallacy", methods=["POST"])
def classify_fallacy():
    print("\n[CLASSIFY_FALLACY] ==== Endpoint called ====")
    data = request.get_json(force=True)
    argument_text = data.get("argument_text")
    print(f"[CLASSIFY_FALLACY] argument_text: {argument_text[:100] if argument_text else 'None'}")
    local_model = data.get("local_model", "electra-logic")
    mappings_csv = data.get("mappings_csv")
    topk = int(data.get("topk", 5))

    if not argument_text:
        return jsonify({"error": "Missing argument_text"}), 400

    # Build fallacy list for LLM prompt from the 13 canonical fallacies
    fallacy_names = [f["name"] for f in FALLACY_LIST]
    fallacy_descriptions = "\n".join([
        f"- {f['name']} ({f['alias']}): {f['description']}" 
        for f in FALLACY_LIST
    ])

    # 1) LLM-based classification (constrained to 13 fallacies)
    system_role = (
        "You are a logical fallacy classifier. You must ONLY detect fallacies from the provided list. "
        "Return valid JSON with key 'predictions' as an array of objects with 'label' (fallacy name) and 'score' (0-1 confidence)."
    )
    prompt = f"""Analyze the following argument and classify it into the most likely logical fallacies from this list:

{fallacy_descriptions}

Argument:
{argument_text}

Return ONLY valid JSON in this exact format:
{{
  "predictions": [
    {{"label": "Fallacy Name", "score": 0.95}},
    {{"label": "Another Fallacy", "score": 0.78}}
  ]
}}

Rules:
- ONLY use fallacy names from the list above
- Return top 5 most likely fallacies
- Scores must be between 0 and 1
- Sort by score (highest first)
"""

    llm_result_raw = llm_completion(system_role, prompt, json_mode=True)
    llm_predictions = None
    if llm_result_raw:
        try:
            print(f"[DEBUG] llm_result_raw received (first 800 chars): {llm_result_raw[:800]}")
            parsed = json.loads(llm_result_raw)
            print(f"[DEBUG] Parsed JSON type: {type(parsed)}, keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'N/A'}")
            
            if isinstance(parsed, dict) and "predictions" in parsed:
                llm_predictions = parsed["predictions"]
                print(f"[DEBUG] Found predictions array with {len(llm_predictions)} items")
            elif isinstance(parsed, list):
                llm_predictions = parsed
                print(f"[DEBUG] Found list with {len(llm_predictions)} items")
            else:
                # Fallback: try to extract fallacy names and scores
                if isinstance(parsed, dict):
                    preds = []
                    for k, v in parsed.items():
                        # Case-insensitive matching
                        if k.lower() in [f.lower() for f in fallacy_names]:
                            try:
                                preds.append({"label": k, "score": float(v)})
                            except Exception:
                                continue
                    if preds:
                        llm_predictions = preds
                        print(f"[DEBUG] Extracted {len(preds)} predictions from dict")
            
            # Filter to only include valid fallacy names (case-insensitive) and sort by score
            if llm_predictions:
                # Create normalized mapping for robust matching (handles parentheses/punctuation)
                fallacy_name_map = {_normalize_label(f): f for f in fallacy_names}
                filtered_preds = []

                for p in llm_predictions:
                    label = p.get("label", "")
                    label_norm = _normalize_label(label)
                    if label_norm in fallacy_name_map:
                        # Use the canonical name
                        filtered_preds.append({
                            "label": fallacy_name_map[label_norm],
                            "score": p.get("score", 0)
                        })
                    else:
                        print(f"[DEBUG] Filtered out label '{label}' - not in fallacy list")
                
                print(f"[DEBUG] After filtering: {len(filtered_preds)} predictions remain")
                llm_predictions = filtered_preds
                llm_predictions.sort(key=lambda x: x.get("score", 0), reverse=True)
                llm_predictions = llm_predictions[:5]  # Top 5
                print(f"[DEBUG] Final LLM predictions: {llm_predictions}")
                
        except Exception as e:
            print(f"[ERROR] Error parsing LLM response: {e}")
            import traceback
            traceback.print_exc()
            llm_predictions = None
    else:
        print(f"[ERROR] llm_completion returned None for argument: {argument_text[:100]}")
        llm_predictions = None

    # 2) Local model classification
    try:
        local_preds = classify_with_local_model(argument_text, local_model, mappings_csv=mappings_csv, topk=topk)
    except Exception as e:
        print(f"[ERROR] Local classification failed: {e}")
        local_preds = []

    # Return only the local model's detections to the frontend as the
    # authoritative 'fallacies_detected' list. This removes the side-by-side
    # comparison between API (LLM) and local model.
    return jsonify({
        "fallacies_detected": local_preds
    })

@app.route("/api/evaluate_user_response", methods=["POST"])
def evaluate_user_response():
    data = request.get_json(force=True)
    opponent_argument = data.get("opponent_argument")
    user_response = data.get("user_response")

    if not opponent_argument or not user_response:
        return jsonify({"error": "Missing opponent_argument or user_response"}), 400

    template = templates.get("evaluate_user_response")
    if not template:
        return jsonify({"error": "Template not found"}), 500

    prompt = (
        template["prompt"]
        .replace("{{OPPONENT_ARGUMENT}}", opponent_argument)
        .replace("{{USER_RESPONSE}}", user_response)
    )

    result = llm_completion(template["role"], prompt)
    if result is None:
        return jsonify({"error": "LLM failed"}), 500

    try:
        return jsonify(json.loads(result))
    except json.JSONDecodeError:
        return jsonify({"raw_response": result})

@app.route("/api/get_chat_history", methods=["GET"])
def get_chat_history():
    try:
        if os.path.exists(DB_PATH):
            with open(DB_PATH, "r", encoding="utf-8") as f:
                db_data = json.load(f)
            return jsonify(db_data)
        else:
            return jsonify({"chats": []})
    except Exception as e:
        print(f"[ERROR] Error reading chat history: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/save_chat", methods=["POST"])
def save_chat():
    try:
        data = request.get_json(force=True)
        chat_id = data.get("chat_id")
        new_entry = data.get("entry")
        
        if not new_entry:
             return jsonify({"error": "Missing entry data"}), 400
        
        if os.path.exists(DB_PATH):
            with open(DB_PATH, "r", encoding="utf-8") as f:
                try:
                    db_data = json.load(f)
                except json.JSONDecodeError:
                    db_data = {"chats": []}
        else:
            db_data = {"chats": []}
            
        # Ensure structure
        if "chats" not in db_data:
            db_data["chats"] = []
            
        target_chat = None
        
        # Try to find existing chat
        if chat_id:
            for chat in db_data["chats"]:
                if chat["chat_id"] == chat_id:
                    target_chat = chat
                    break
        
        # Create new chat if not found or no ID provided
        if not target_chat:
            # Generate title from the first argument text
            first_arg_text = new_entry.get("raw_text", "")
            title = generate_chat_title(first_arg_text)
            
            new_chat_id = "chat_" + str(os.urandom(4).hex())
            target_chat = {
                "chat_id": new_chat_id,
                "title": title,
                "created_at": new_entry.get("timestamp"),
                "arguments": []
            }
            # Prepend to list so it shows at top
            db_data["chats"].insert(0, target_chat)
            
        # Add the new argument/interaction
        target_chat["arguments"].append(new_entry)
        
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(db_data, f, indent=2)
            
        return jsonify({
            "status": "success", 
            "chat_id": target_chat["chat_id"],
            "title": target_chat["title"]
        })
    except Exception as e:
        print(f"[ERROR] Error saving chat: {e}")
        return jsonify({"error": str(e)}), 500

# ==============================
# Debug Endpoint - Check LLM Status
# ==============================
@app.route("/api/debug/llm_status", methods=["GET"])
def llm_status():
    """Returns current LLM configuration and status for debugging."""
    return jsonify({
        "api_key_set": bool(OPENROUTER_API_KEY),
        "api_key_preview": f"{OPENROUTER_API_KEY[:15]}...{OPENROUTER_API_KEY[-5:]}" if OPENROUTER_API_KEY else None,
        "use_llm": USE_LLM,
        "models_available": FREE_MODELS,
        "rate_limited": _RATE_LIMITED,
        "rate_limit_message": _RATE_LIMIT_MSG,
        "last_error": _LAST_LLM_ERROR
    })

@app.route("/api/debug/test_llm", methods=["GET"])
def test_llm():
    """Quick test of the LLM connection."""
    result = llm_completion(
        "You are a helpful assistant.",
        "Say 'LLM is working!' in a JSON object with key 'status'.",
        json_mode=True
    )
    if result:
        return jsonify({"success": True, "response": result})
    else:
        return jsonify({
            "success": False, 
            "error": _LAST_LLM_ERROR,
            "rate_limited": _RATE_LIMITED
        }), 500

# ==============================
# Run App
# ==============================
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, port=5000)
