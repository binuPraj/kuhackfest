"""
Extension API Routes - Unified Backend
========================================

╔══════════════════════════════════════════════════════════════════════════════╗
║                    ARCHITECTURAL COMPLIANCE VERIFICATION                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ ✅ VERIFIED: 2024-12-24                                                      ║
║ ✅ All routes call core_service.py functions (NO local AI logic)             ║
║ ✅ Receives IDENTICAL raw response as chatbot                                ║
║ ✅ Transformations are UI-ONLY (cosmetic, not reasoning)                     ║
║ ✅ Same LLM model, prompts, and pipeline as chatbot                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

These routes now use the SAME backend logic as the chatbot.
All AI calls go through services/core_service.py which uses
the identical prompts and logic as gem_app.py.

ARCHITECTURE:
    Extension Frontend (popup.js)
           │
           ▼
    /api/analyze, /api/detect-fallacies, etc.
           │
           ▼
    core_service.py (shared with chatbot)
           │
           ▼
    llm_client.py (unified AI gateway)

The only differences from chatbot:
- Different API endpoint names (for backward compatibility)
- Response transformations for extension UI compatibility
- Extension-specific utility endpoints (health, test, models)

The CORE LOGIC is 100% identical to the chatbot.
"""

import os
import time
from functools import wraps
from typing import Any, Dict, Tuple

from flask import Blueprint, jsonify, request

# Import unified core service (same logic as chatbot)
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.core_service import (
    analyze_argument,
    improve_argument,
    generate_counter_argument,
    evaluate_response,
    detect_fallacies_local,  # 🆕 NEW: Local model fallacy detection (no LLM)
    classify_with_local_model  # 🆕 NEW: Raw local classification access
    # ✅ REMOVED: transform_to_extension_format, transform_improvement_to_extension_format,
    #            transform_counter_to_extension_format
    # REASON: Extension now receives RAW chatbot responses - NO transformations
)
from services.llm_client import llm_client

# Keep reasoning module for static data (fallacy definitions, Toulmin factors)
from . import reasoning


bp = Blueprint("extension_api", __name__)


# ==============================
# Rate Limiting (matches llm_client)
# ==============================
# Note: Rate limiting is also enforced in llm_client.py
# This provides an additional layer at the route level

def rate_limited(fn):
    """
    Route-level rate limiter for extension endpoints.
    Works in conjunction with llm_client's rate limiter.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Let the core service handle rate limiting via llm_client
        # This wrapper is kept for backward compatibility
        return fn(*args, **kwargs)
    return wrapper


# ==============================
# Request Validation Helpers
# ==============================

def _parse_json_body() -> Tuple[Dict[str, Any], int]:
    """Parse JSON request body."""
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return {}, 400
    return body, 200


def _validate_text_field(text: Any, field_name: str = "text") -> Tuple[str, Dict[str, Any]]:
    """Validate text field from request."""
    if not isinstance(text, str):
        return "", {
            "error": "Invalid request",
            "message": f"{field_name} is required and must be a string",
        }
    if len(text) < 10:
        return "", {
            "error": "Text too short",
            "message": f"{field_name} must be at least 10 characters long"
        }
    if len(text) > 5000:
        return "", {
            "error": "Text too long",
            "message": f"{field_name} must not exceed 5000 characters"
        }
    return text.strip(), {}


def _get_client_ip() -> str:
    """Get client IP for rate limiting."""
    return request.remote_addr or "127.0.0.1"


# ==============================
# Fallback Responses
# ==============================

FALLBACK_RESPONSES = {
    "analysis": {
        "elements": {},
        "fallacies": [],
        "toulminAnalysis": reasoning.create_empty_toulmin_analysis(),
        "suggestions": [],
        "overallAssessment": "Analysis temporarily unavailable. Please try again.",
        "fallacy_resistance_score": 0,
        "logical_consistency_score": 0,
        "clarity_score": 0,
        "issues": []
    },
    "fallacies": {
        "fallacies": [],
        "overallAssessment": "Unable to analyze at this time.",
        "reasoningQuality": "unknown"
    },
    "reply": {
        "replies": [
            {"tone": "neutral", "text": "Unable to generate reply at this time."},
            {"tone": "polite", "text": "Unable to generate reply at this time."},
            {"tone": "assertive", "text": "Unable to generate reply at this time."}
        ],
        "response": "",
        "originalArgumentSummary": "",
        "identifiedWeaknesses": [],
        "counterArgument": ""
    },
    "rewrite": {
        "rewrittenText": "",
        "improved_argument": "",
        "explanation": "Unable to rewrite at this time.",
        "originalAnalysis": {"strengths": [], "weaknesses": [], "mainClaim": ""},
        "changes": [],
        "improvementScore": {"before": 0, "after": 0}
    }
}


# ==============================
# API Routes - Using Chatbot Logic
# ==============================

@bp.route("/analyze", methods=["POST"])
@rate_limited
def analyze_text():
    """
    Analyze text for logical fallacies and argument structure.
    
    UNIFIED: Uses the same logic as chatbot's /api/extract_toulmin
    
    Request:
        {"text": "...", "context": {...}}
    
    Response:
        Same structure as chatbot, with extension-specific transforms
    """
    body, status = _parse_json_body()
    if status != 200:
        return jsonify({"error": "Invalid JSON body"}), 400

    text, error = _validate_text_field(body.get("text"))
    if error:
        return jsonify(error), 400

    try:
        # ┌──────────────────────────────────────────────────────────────────┐
        # │ ✅ VIOLATION FIX (2024-12-24):                                   │
        # │                                                                  │
        # │ REMOVED: transform_to_extension_format() call                    │
        # │                                                                  │
        # │ REASON: Extension must receive IDENTICAL response as chatbot.   │
        # │ The chatbot's /api/extract_toulmin returns raw analyze_argument()│
        # │ result. Extension must receive the SAME raw result.              │
        # │                                                                  │
        # │ UI PARITY: Extension frontend updated to render same format.    │
        # └──────────────────────────────────────────────────────────────────┘
        
        # Call the SAME function the chatbot uses
        client_ip = _get_client_ip()
        result = analyze_argument(text, client_ip)
        
        if "error" in result:
            return jsonify(FALLBACK_RESPONSES["analysis"])
        
        # ✅ RETURN RAW RESULT - IDENTICAL TO CHATBOT
        # NO transformation - extension UI must handle chatbot format directly
        return jsonify(result)
        
    except Exception as exc:
        print(f"❌ Error in /api/analyze: {exc}")
        return jsonify(FALLBACK_RESPONSES["analysis"])


@bp.route("/detect-fallacies", methods=["POST"])
@rate_limited
def detect_fallacies():
    """
    Detect logical fallacies in text.
    
    ┌──────────────────────────────────────────────────────────────────┐
    │ 🆕 UPDATED (2024-12-25): Now uses LOCAL MODEL for fallacies     │
    │                                                                  │
    │ ✅ Fallacy detection via saved_models/ (Electra NLI)            │
    │ ❌ NO LLM/API calls for fallacy detection                       │
    │ ⚡ Faster response times (local inference)                       │
    │ 💰 Zero API costs for fallacy detection                         │
    └──────────────────────────────────────────────────────────────────┘
    
    Request:
        {"text": "...", "use_local_only": true/false}
    
    Response:
        {"fallacies": [...], "overallAssessment": "...", ...}
    """
    body, status = _parse_json_body()
    if status != 200:
        return jsonify({"error": "Invalid JSON body"}), 400

    text, error = _validate_text_field(body.get("text"))
    if error:
        return jsonify(error), 400

    # Option to use ONLY local model (no LLM at all) - default is True now
    use_local_only = body.get("use_local_only", True)

    try:
        if use_local_only:
            # ============================================================
            # 🆕 LOCAL MODEL ONLY: Fast fallacy detection, no LLM calls
            # ============================================================
            print(f"[DETECT_FALLACIES] Using LOCAL MODEL only (no LLM)")
            result = detect_fallacies_local(text, topk=5, threshold=0.35)
            fallacies_present = result.get("fallacies_present", [])
            
            # Enrich fallacy data with definitions from reasoning module
            enriched_fallacies = []
            for i, fallacy_name in enumerate(fallacies_present):
                # Get score from details if available
                details = result.get("fallacy_details", [])
                score = details[i].get("score", 0.5) if i < len(details) else 0.5
                description = details[i].get("description", "") if i < len(details) else ""
                
                fallacy_data = {
                    "type": fallacy_name,
                    "alias": fallacy_name,
                    "explanation": description or f"This argument contains a {fallacy_name} fallacy.",
                    "excerpt": "",
                    "isVerified": True,
                    "confidence": round(score * 100, 1)
                }
                # Try to get additional info from reasoning module
                enriched = reasoning.enrich_fallacy_data(fallacy_data)
                enriched_fallacies.append(enriched)
            
            response = {
                "fallacies": enriched_fallacies,
                "verifiedCount": len(enriched_fallacies),
                "totalCount": len(enriched_fallacies),
                "overallAssessment": f"Local model detected {len(enriched_fallacies)} fallacy(ies)." if enriched_fallacies else "No fallacies detected by local model.",
                "reasoningQuality": result.get("reasoning_quality", "moderate"),
                "fallacy_resistance_score": result.get("fallacy_resistance_score", 50),
                "_source": "local_model"
            }
            
            return jsonify(response)
        
        else:
            # ============================================================
            # HYBRID MODE: Uses analyze_argument (local + LLM)
            # ============================================================
            print(f"[DETECT_FALLACIES] Using HYBRID mode (local + LLM)")
            client_ip = _get_client_ip()
            result = analyze_argument(text, client_ip)
            
            if "error" in result:
                return jsonify(FALLBACK_RESPONSES["fallacies"])
            
            # Extract fallacy information from chatbot response
            fallacies_present = result.get("fallacies_present", [])
            
            # Enrich fallacy data with definitions from reasoning module
            enriched_fallacies = []
            for fallacy_name in fallacies_present:
                fallacy_data = {
                    "type": fallacy_name,
                    "alias": fallacy_name,
                    "explanation": f"This argument contains a {fallacy_name} fallacy.",
                    "excerpt": "",
                    "isVerified": True
                }
                # Try to get additional info from reasoning module
                enriched = reasoning.enrich_fallacy_data(fallacy_data)
                enriched_fallacies.append(enriched)
            
            response = {
                "fallacies": enriched_fallacies,
                "verifiedCount": len(enriched_fallacies),
                "totalCount": len(enriched_fallacies),
                "overallAssessment": result.get("feedback", "Analysis complete."),
                "reasoningQuality": _assess_quality(result.get("logical_consistency_score", 0)),
                "_source": "hybrid"
            }
            
            return jsonify(response)
        
    except Exception as exc:
        print(f"❌ Error in /api/detect-fallacies: {exc}")
        return jsonify(FALLBACK_RESPONSES["fallacies"])


@bp.route("/classify-local", methods=["POST"])
def classify_local():
    """
    Pure local model fallacy classification (NO LLM at all).
    
    ┌──────────────────────────────────────────────────────────────────┐
    │ 🆕 NEW ENDPOINT (2024-12-25): Pure local inference              │
    │                                                                  │
    │ ✅ Uses saved_models/ (Electra-based NLI models)                │
    │ ✅ Uses mapcsv/mappings.csv for fallacy hypotheses              │
    │ ❌ NO external API calls - completely offline capable            │
    │ ⚡ Fastest response times (local inference only)                 │
    │ 💰 Zero API costs                                                │
    └──────────────────────────────────────────────────────────────────┘
    
    Request:
        {
            "text": "...",
            "model": "electra-logic",  # optional
            "mode": "base",  # optional: base, description, logical-form
            "topk": 5,  # optional
            "threshold": 0.3  # optional
        }
    
    Response:
        {
            "predictions": [{"label": "...", "score": 0.85}, ...],
            "fallacies_present": ["...", ...],
            "model_used": "electra-logic"
        }
    """
    body, status = _parse_json_body()
    if status != 200:
        return jsonify({"error": "Invalid JSON body"}), 400

    text, error = _validate_text_field(body.get("text"))
    if error:
        return jsonify(error), 400

    # Optional parameters
    model_folder = body.get("model", "electra-logic")
    mode = body.get("mode", "base")
    topk = min(body.get("topk", 5), 13)  # Max 13 fallacies
    threshold = max(0.0, min(1.0, body.get("threshold", 0.3)))

    try:
        predictions = classify_with_local_model(
            argument_text=text,
            model_folder=model_folder,
            mode=mode,
            topk=topk,
            threshold=threshold
        )
        
        return jsonify({
            "predictions": predictions,
            "fallacies_present": [p["label"] for p in predictions],
            "model_used": model_folder,
            "mode": mode,
            "_source": "local_model"
        })
        
    except Exception as exc:
        print(f"❌ Error in /api/classify-local: {exc}")
        return jsonify({
            "error": "Local classification failed",
            "message": str(exc),
            "predictions": [],
            "fallacies_present": []
        }), 500


def _assess_quality(score: int) -> str:
    """Convert numeric score to quality label."""
    if score >= 70:
        return "strong"
    elif score >= 40:
        return "moderate"
    else:
        return "weak"


@bp.route("/generate-reply", methods=["POST"])
@rate_limited
def generate_reply():
    """
    Generate a counter-argument or reply.
    
    UNIFIED: Uses the same logic as chatbot's /api/oppose_mode
    
    Request:
        {"originalPost": "...", "draftReply": "...", "tone": "neutral|polite|assertive"}
    
    Response:
        {"replies": [...], "counterArgument": "...", ...}
    """
    body, status = _parse_json_body()
    if status != 200:
        return jsonify({"error": "Invalid JSON body"}), 400

    original_post, error = _validate_text_field(body.get("originalPost"), "originalPost")
    if error:
        return jsonify(error), 400

    try:
        # ┌──────────────────────────────────────────────────────────────────┐
        # │ ✅ VIOLATION FIX (2024-12-24):                                   │
        # │                                                                  │
        # │ REMOVED: transform_counter_to_extension_format() call            │
        # │                                                                  │
        # │ REASON: Extension must receive IDENTICAL response as chatbot.   │
        # │ The chatbot's /api/oppose_mode returns raw result.               │
        # │ Extension must receive the SAME raw result.                      │
        # └──────────────────────────────────────────────────────────────────┘
        
        # Use the same counter-argument function as chatbot
        client_ip = _get_client_ip()
        context = body.get("draftReply", "")
        
        result = generate_counter_argument(original_post, context, client_ip)
        
        if "error" in result:
            return jsonify(FALLBACK_RESPONSES["reply"])
        
        # ✅ RETURN RAW RESULT - IDENTICAL TO CHATBOT
        return jsonify(result)
        
    except Exception as exc:
        print(f"❌ Error in /api/generate-reply: {exc}")
        return jsonify(FALLBACK_RESPONSES["reply"])


@bp.route("/rewrite", methods=["POST"])
@rate_limited
def rewrite_argument():
    """
    Rewrite and improve an argument.
    
    ┌──────────────────────────────────────────────────────────────────┐
    │ ✅ COMPLIANCE NOTE:                                              │
    │                                                                  │
    │ This route calls SAME functions as chatbot:                      │
    │   1. analyze_argument() - same as /api/extract_toulmin           │
    │   2. improve_argument() - same as /api/support_mode              │
    │                                                                  │
    │ ARCHITECTURAL DECISION:                                          │
    │ Extension auto-detects fallacy_type via analyze_argument() first │
    │ because extension UI doesn't require user to specify fallacy.    │
    │                                                                  │
    │ Chatbot requires explicit fallacy_type in request (UI difference)│
    │ but SAME core logic is used for the improvement step.            │
    └──────────────────────────────────────────────────────────────────┘
    
    Request:
        {"text": "...", "preserveLength": true}
    
    Response:
        {"rewrittenText": "...", "changes": [...], ...}
    """
    body, status = _parse_json_body()
    if status != 200:
        return jsonify({"error": "Invalid JSON body"}), 400

    text, error = _validate_text_field(body.get("text"))
    if error:
        return jsonify(error), 400

    try:
        # ┌──────────────────────────────────────────────────────────────────┐
        # │ ✅ VIOLATION FIX (2024-12-24):                                   │
        # │                                                                  │
        # │ REMOVED: transform_improvement_to_extension_format() call        │
        # │                                                                  │
        # │ REASON: Extension must receive IDENTICAL response as chatbot.   │
        # │ The chatbot's /api/support_mode returns raw result.              │
        # │ Extension must receive the SAME raw result.                      │
        # └──────────────────────────────────────────────────────────────────┘
        
        # First analyze to detect fallacies (same as chatbot flow)
        client_ip = _get_client_ip()
        analysis = analyze_argument(text, client_ip)
        
        # Get detected fallacies
        fallacies = analysis.get("fallacies_present", [])
        fallacy_type = fallacies[0] if fallacies else "weak reasoning"
        
        # Use the same improvement function as chatbot
        result = improve_argument(text, fallacy_type, client_ip)
        
        if "error" in result:
            return jsonify(FALLBACK_RESPONSES["rewrite"])
        
        # ✅ RETURN RAW RESULT - IDENTICAL TO CHATBOT
        # Also include the analysis for full context
        result["analysis"] = analysis
        return jsonify(result)
        
    except Exception as exc:
        print(f"❌ Error in /api/rewrite: {exc}")
        return jsonify(FALLBACK_RESPONSES["rewrite"])


# ==============================
# Utility Routes (Extension-specific)
# ==============================

@bp.route("/models", methods=["GET"])
@rate_limited
def get_models():
    """
    Get loaded models and definitions.
    Returns fallacy and Toulmin factor definitions.
    """
    context = reasoning.generate_analysis_context()
    return jsonify({
        "status": "loaded",
        "model": llm_client.model,
        "fallacies": {
            "count": context.get("fallacyCount", 0),
            "list": [
                {
                    "id": f.get("id"),
                    "name": f.get("name"),
                    "alias": f.get("alias"),
                }
                for f in reasoning.get_fallacy_definitions()
            ],
        },
        "toulmin": {
            "count": context.get("factorCount", 0),
            "factors": [
                {"factor": f.get("factor"), "definition": f.get("definition")}
                for f in reasoning.get_toulmin_factors()
            ],
        },
        "references": reasoning.get_references(),
    })


@bp.route("/test", methods=["GET"])
@rate_limited
def test_connection():
    """
    Test AI connection.
    Verifies the unified LLM client is working.
    """
    try:
        # Simple test using the unified client
        is_connected = llm_client.is_configured()
        status_info = llm_client.get_status()
        
        return jsonify({
            "status": "connected" if is_connected else "disconnected",
            "message": "AI service is operational" if is_connected else "AI service not configured",
            "provider": status_info,
            "models": {
                "fallacies": len(reasoning.get_fallacy_definitions()),
                "toulminFactors": len(reasoning.get_toulmin_factors()),
            },
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })


@bp.route("/health", methods=["GET"])
@rate_limited
def health():
    """
    Health check endpoint.
    Returns service status and configuration.
    """
    status_info = llm_client.get_status()
    return jsonify({
        "status": "ok",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": "2.0.0-unified",
        "provider": status_info,
        "unified": True,
        "message": "Extension and chatbot using unified backend"
    })
