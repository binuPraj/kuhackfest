"""
Unified Flask Backend - gem_app.py
===================================

╔══════════════════════════════════════════════════════════════════════════════╗
║                    ARCHITECTURAL COMPLIANCE VERIFICATION                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ ✅ VERIFIED: 2024-12-24                                                      ║
║ ✅ Both chatbot and extension routes call SAME core_service functions        ║
║ ✅ Chatbot response format is UNCHANGED from original                        ║
║ ✅ Extension routes return identical raw data (with UI transforms)           ║
║ ✅ ZERO AI logic in route handlers - all delegated to core_service           ║
║ ✅ Single Flask app serves both clients                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

This is the MAIN entry point for both the chatbot and browser extension.
All routes use the same core service layer for consistent behavior.

ARCHITECTURE:
┌─────────────────────────────────────────────────────────────────┐
│                        gem_app.py                               │
│                    (Flask Application)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Chatbot Routes              Extension Routes                  │
│   (/api/extract_toulmin)      (/api/analyze)                   │
│   (/api/support_mode)         (/api/detect-fallacies)          │
│   (/api/oppose_mode)          (/api/generate-reply)            │
│   (/api/evaluate_user_response) (/api/rewrite)                 │
│            │                           │                        │
│            └───────────┬───────────────┘                        │
│                        ▼                                        │
│            ┌─────────────────────┐                             │
│            │  services/          │                             │
│            │  core_service.py    │  ← SINGLE SOURCE OF TRUTH   │
│            └──────────┬──────────┘                             │
│                       ▼                                        │
│            ┌─────────────────────┐                             │
│            │  services/          │                             │
│            │  llm_client.py      │  ← UNIFIED AI GATEWAY       │
│            └─────────────────────┘                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

USAGE:
    python gem_app.py
    
    Starts server on http://localhost:5001
    Both chatbot and extension connect to this single server.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from dotenv import load_dotenv

# Import extension blueprint (uses core_service internally)
from extension import extension_bp

# Import unified services
from services.llm_client import llm_client
from services.core_service import (
    analyze_argument,
    analyze_argument_dual_mode,  # 🆕 NEW: Dual-mode unified response (support + defence)
    improve_argument,
    generate_counter_argument,
    evaluate_response,
    generate_chat_title,
    # 🆕 NEW: Local model fallacy classification (no LLM)
    classify_with_local_model,
    detect_fallacies_local,
    get_detected_fallacies
)

# ==============================
# Load environment variables
# ==============================
load_dotenv()

# ==============================
# Flask App Configuration
# ==============================
app = Flask(__name__)
CORS(app)

# Register extension blueprint (provides /api/analyze, /api/detect-fallacies, etc.)
app.register_blueprint(extension_bp, url_prefix="/api")

# ==============================
# Database Configuration
# ==============================
DB_PATH = os.path.join(os.path.dirname(__file__), "../public/data/db.json")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


# ==============================
# Helper: Recalculate Global Insights
# ==============================
def recalculate_insights(db_data):
    """
    Recalculate aggregate insights from all arguments across all chats.
    Updates the 'insights' object in db_data with averages.
    """
    total_fallacy_resistance = 0
    total_logical_consistency = 0
    total_clarity = 0
    radar_totals = {"claim": 0, "data": 0, "warrant": 0, "backing": 0, "qualifier": 0, "rebuttal": 0}
    fallacy_counts = {}
    support_mode_count = 0
    
    for chat in db_data.get("chats", []):
        for arg in chat.get("arguments", []):
            if arg.get("mode_used") != "support":
                continue
                
            response = arg.get("response", {})
            if not response or not isinstance(response, dict):
                continue
            
            if "elements" not in response:
                continue
                
            support_mode_count += 1
            
            total_fallacy_resistance += response.get("fallacy_resistance_score", 0)
            total_logical_consistency += response.get("logical_consistency_score", 0)
            total_clarity += response.get("clarity_score", 0)
            
            elements = response.get("elements", {})
            for key in radar_totals:
                element = elements.get(key, {})
                if isinstance(element, dict):
                    radar_totals[key] += element.get("strength", 0)
            
            for fallacy in response.get("fallacies_present", []):
                fallacy_counts[fallacy] = fallacy_counts.get(fallacy, 0) + 1
    
    if support_mode_count > 0:
        avg_fallacy_resistance = round(total_fallacy_resistance / support_mode_count, 1)
        avg_logical_consistency = round(total_logical_consistency / support_mode_count, 1)
        avg_clarity = round(total_clarity / support_mode_count, 1)
        avg_radar = {k: round(v / support_mode_count, 1) for k, v in radar_totals.items()}
    else:
        avg_fallacy_resistance = 0
        avg_logical_consistency = 0
        avg_clarity = 0
        avg_radar = {k: 0 for k in radar_totals}
    
    sorted_fallacies = sorted(fallacy_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    common_fallacies = [{"type": f[0], "count": f[1]} for f in sorted_fallacies]
    
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
# API ROUTES - Chatbot Endpoints
# ==============================
# These routes use core_service.py which is SHARED with the extension.
# The extension routes (/api/analyze, etc.) call the SAME core functions.

@app.route("/", methods=["GET"])
def index():
    """Root endpoint - shows API status and available endpoints."""
    return jsonify({
        "name": "COGNIX - Unified Reasoning Assistant API",
        "version": "2.2.0-dual-mode",
        "status": "operational",
        "model": llm_client.model,
        "unified": True,
        "local_fallacy_detection": True,
        "dual_mode_enabled": True,
        "message": "Chatbot and Extension share the same backend logic. Fallacy detection uses LOCAL model (no LLM). Dual-mode returns both support + defence in ONE request.",
        "endpoints": {
            "chatbot": {
                "analyze_dual": "POST /api/analyze_dual → 🆕 DUAL-MODE: Returns both support + defence in ONE request",
                "extract_toulmin": "POST /api/extract_toulmin (legacy - use analyze_dual)",
                "support_mode": "POST /api/support_mode (legacy - use analyze_dual)",
                "oppose_mode": "POST /api/oppose_mode (legacy - use analyze_dual)",
                "evaluate_user_response": "POST /api/evaluate_user_response",
                "get_chat_history": "GET /api/get_chat_history",
                "save_chat": "POST /api/save_chat",
                "classify_fallacy": "POST /api/classify_fallacy → LOCAL MODEL (no LLM)"
            },
            "extension": {
                "analyze": "POST /api/analyze → Same logic as extract_toulmin",
                "detect_fallacies": "POST /api/detect-fallacies → LOCAL MODEL (no LLM)",
                "classify_local": "POST /api/classify-local → Pure local inference",
                "generate_reply": "POST /api/generate-reply → Same logic as oppose_mode",
                "rewrite": "POST /api/rewrite → Same logic as support_mode",
                "models": "GET /api/models",
                "health": "GET /api/health",
                "test": "GET /api/test"
            },
            "debug": {
                "local_model_status": "GET /api/debug/local_model_status → Check local model status"
            }
        }
    })


@app.route("/api/extract_toulmin", methods=["POST"])
def extract_toulmin():
    """
    Analyze an argument using the Toulmin model.
    
    CORE LOGIC: services/core_service.py → analyze_argument()
    This is the SAME function called by /api/analyze for the extension.
    
    Request:
        {"argument_text": "..."}
    
    Response:
        {
            "elements": {...},
            "fallacy_resistance_score": 0-100,
            "logical_consistency_score": 0-100,
            "clarity_score": 0-100,
            "fallacies_present": [...],
            "improved_statement": "...",
            "feedback": "..."
        }
    """
    data = request.get_json(force=True)
    argument_text = data.get("argument_text")

    if not argument_text:
        return jsonify({"error": "Missing argument_text"}), 400

    client_ip = request.remote_addr or "127.0.0.1"
    
    # Use unified core service
    result = analyze_argument(argument_text, client_ip)
    
    if "error" in result:
        return jsonify(result), 500

    return jsonify(result)


@app.route("/api/support_mode", methods=["POST"])
def support_mode():
    """
    Improve an argument by removing fallacies (Support Mode).
    
    CORE LOGIC: services/core_service.py → improve_argument()
    This is the SAME function called by /api/rewrite for the extension.
    
    Request:
        {"argument_text": "...", "fallacy_type": "..."}
    
    Response:
        {"improved_argument": "...", "explanation": "..."}
    """
    data = request.get_json(force=True)
    argument_text = data.get("argument_text")
    fallacy_type = data.get("fallacy_type")

    if not argument_text or not fallacy_type:
        return jsonify({"error": "Missing argument_text or fallacy_type"}), 400

    client_ip = request.remote_addr or "127.0.0.1"
    
    # Use unified core service
    result = improve_argument(argument_text, fallacy_type, client_ip)
    
    if "error" in result:
        return jsonify(result), 500

    return jsonify(result)


@app.route("/api/oppose_mode", methods=["POST"])
def oppose_mode():
    """
    Generate a counter-argument (Oppose Mode).
    
    CORE LOGIC: services/core_service.py → generate_counter_argument()
    This is the SAME function called by /api/generate-reply for the extension.
    
    Request:
        {"argument_text": "...", "context": "..."}
    
    Response:
        {"response": "..."}
    """
    data = request.get_json(force=True)
    argument_text = data.get("argument_text")
    context = data.get("context", "")

    if not argument_text:
        return jsonify({"error": "Missing argument_text"}), 400

    client_ip = request.remote_addr or "127.0.0.1"
    
    # Use unified core service
    result = generate_counter_argument(argument_text, context, client_ip)
    
    if "error" in result:
        return jsonify(result), 500

    return jsonify(result)


@app.route("/api/evaluate_user_response", methods=["POST"])
def evaluate_user_response_route():
    """
    Evaluate how well a user responded to a fallacious argument.
    
    CORE LOGIC: services/core_service.py → evaluate_response()
    
    Request:
        {"opponent_argument": "...", "user_response": "..."}
    
    Response:
        {
            "detected_fallacy": "...",
            "user_countered_correctly": true/false,
            "toulmin_scores": {...},
            "overall_reasoning_score": 0-100,
            "analysis_notes": "..."
        }
    """
    data = request.get_json(force=True)
    opponent_argument = data.get("opponent_argument")
    user_response = data.get("user_response")

    if not opponent_argument or not user_response:
        return jsonify({"error": "Missing opponent_argument or user_response"}), 400

    client_ip = request.remote_addr or "127.0.0.1"
    
    # Use unified core service
    result = evaluate_response(opponent_argument, user_response, client_ip)
    
    if "error" in result:
        return jsonify(result), 500

    return jsonify(result)


# ==============================
# 🆕 DUAL-MODE UNIFIED ENDPOINT
# ==============================
# ┌──────────────────────────────────────────────────────────────────────────────┐
# │ ARCHITECTURAL DESIGN: SINGLE REQUEST, DUAL OUTPUT                           │
# │                                                                              │
# │ This endpoint is the CORNERSTONE of the unified reasoning architecture.     │
# │ It enables:                                                                  │
# │   • Dedicated Chatbot (current)                                             │
# │   • Floating Chatbot (future)                                               │
# │   • Real-time Suggestions (future)                                          │
# │                                                                              │
# │ All clients submit ONE request and receive BOTH support + defence responses.│
# │ Mode switching happens ENTIRELY on the frontend - NO additional API calls.  │
# │                                                                              │
# │ ⚠️ REGRESSION PREVENTION:                                                   │
# │    Do NOT add mode-specific endpoints or client branching.                  │
# │    All reasoning perspectives come from THIS single endpoint.               │
# └──────────────────────────────────────────────────────────────────────────────┘

@app.route("/api/analyze_dual", methods=["POST"])
def analyze_dual():
    """
    🆕 DUAL-MODE UNIFIED ENDPOINT: Analyze argument and return BOTH modes.
    
    ═══════════════════════════════════════════════════════════════════════════════
    CRITICAL ARCHITECTURAL PRINCIPLE:
    ═══════════════════════════════════════════════════════════════════════════════
    
    User submits argument ONCE → Backend generates BOTH support + defence responses
                               → Frontend toggles between them INSTANTLY (no refetch)
    
    This endpoint is REUSABLE across:
    • Dedicated Chatbot (chat.html)
    • Floating Chatbot (future)
    • Real-time Suggestions (future)
    
    NO future backend changes required for these features.
    ═══════════════════════════════════════════════════════════════════════════════
    
    CORE LOGIC: services/core_service.py → analyze_argument_dual_mode()
    
    Request:
        {"argument_text": "..."}
    
    Response:
        {
            "support": {
                "elements": {...},
                "fallacy_resistance_score": 0-100,
                "logical_consistency_score": 0-100,
                "clarity_score": 0-100,
                "fallacies_present": [...],
                "fallacy_details": [...],
                "improved_statement": "...",
                "feedback": "..."
            },
            "defence": {
                "response": "..."
            },
            "_meta": {
                "default_mode": "support",
                "is_dual_mode": true,
                "toggle_is_frontend_only": true
            }
        }
    """
    data = request.get_json(force=True)
    argument_text = data.get("argument_text")

    if not argument_text:
        return jsonify({"error": "Missing argument_text"}), 400

    client_ip = request.remote_addr or "127.0.0.1"
    
    # Use unified core service - generates BOTH modes in ONE call
    result = analyze_argument_dual_mode(argument_text, client_ip)
    
    if "error" in result.get("support", {}):
        return jsonify(result), 500

    return jsonify(result)


# ==============================
# Chat History Routes (Chatbot-specific)
# ==============================

@app.route("/api/get_chat_history", methods=["GET"])
def get_chat_history():
    """Get saved chat history from database."""
    try:
        if os.path.exists(DB_PATH):
            with open(DB_PATH, "r", encoding="utf-8") as f:
                db_data = json.load(f)
            return jsonify(db_data)
        else:
            return jsonify({"chats": []})
    except Exception as e:
        print(f"❌ Error reading chat history: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/save_chat", methods=["POST"])
def save_chat():
    """Save a chat entry to database."""
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
            
        if "chats" not in db_data:
            db_data["chats"] = []
            
        target_chat = None
        
        if chat_id:
            for chat in db_data["chats"]:
                if chat["chat_id"] == chat_id:
                    target_chat = chat
                    break
        
        if not target_chat:
            first_arg_text = new_entry.get("raw_text", "")
            client_ip = request.remote_addr or "127.0.0.1"
            
            # Use unified core service for title generation
            title = generate_chat_title(first_arg_text, client_ip)
            
            new_chat_id = "chat_" + str(os.urandom(4).hex())
            target_chat = {
                "chat_id": new_chat_id,
                "title": title,
                "created_at": new_entry.get("timestamp"),
                "arguments": []
            }
            db_data["chats"].insert(0, target_chat)
            
        target_chat["arguments"].append(new_entry)
        db_data = recalculate_insights(db_data)
        
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(db_data, f, indent=2)
            
        return jsonify({
            "status": "success", 
            "chat_id": target_chat["chat_id"],
            "title": target_chat["title"]
        })
    except Exception as e:
        print(f"❌ Error saving chat: {e}")
        return jsonify({"error": str(e)}), 500


# ==============================
# Local Model Fallacy Classification Endpoint
# ==============================
@app.route("/api/classify_fallacy", methods=["POST"])
def classify_fallacy():
    """
    Classify fallacies using LOCAL model (NO LLM calls).
    
    ┌──────────────────────────────────────────────────────────────────┐
    │ 🆕 NEW ENDPOINT (2024-12-25): Local model fallacy classification │
    │                                                                  │
    │ ✅ Uses saved_models/ (Electra-based NLI models)                 │
    │ ✅ Uses mapcsv/mappings.csv for fallacy hypotheses               │
    │ ❌ NO external API/LLM calls - completely offline                │
    │ ⚡ Fast response times (local inference only)                    │
    │ 💰 Zero API costs                                                │
    └──────────────────────────────────────────────────────────────────┘
    
    Request:
        {
            "argument_text": "...",
            "model_folder": "electra-logic",  # optional
            "mode": "base",  # optional: base, description, logical-form
            "topk": 5  # optional
        }
    
    Response:
        {
            "predictions": [{"label": "...", "score": 0.85}, ...],
            "fallacies_present": ["...", ...],
            "fallacy_resistance_score": 0-100,
            "_source": "local_model"
        }
    """
    try:
        data = request.get_json(force=True)
        argument_text = data.get("argument_text")
        
        if not argument_text:
            return jsonify({"error": "argument_text is required"}), 400
        
        # Optional parameters
        model_folder = data.get("model_folder", "electra-logic")
        mode = data.get("mode", "base")
        topk = min(data.get("topk", 5), 13)
        
        # Use local model classification
        predictions = classify_with_local_model(
            argument_text=argument_text,
            model_folder=model_folder,
            mode=mode,
            topk=topk,
            threshold=0.3
        )
        
        fallacy_names = [p["label"] for p in predictions]
        num_fallacies = len(fallacy_names)
        
        # Calculate resistance score
        if num_fallacies == 0:
            resistance_score = 100
        else:
            resistance_score = max(0, 100 - (num_fallacies * 15))
        
        return jsonify({
            "predictions": predictions,
            "fallacies_present": fallacy_names,
            "fallacy_resistance_score": resistance_score,
            "model_used": model_folder,
            "mode": mode,
            "_source": "local_model"
        })
        
    except Exception as e:
        print(f"❌ Error in classify_fallacy: {e}")
        return jsonify({
            "error": str(e),
            "predictions": [],
            "fallacies_present": [],
            "_source": "local_model"
        }), 500


@app.route("/api/debug/local_model_status", methods=["GET"])
def local_model_status():
    """
    Debug endpoint to check local model status.
    """
    import os as os_module
    
    # Check paths
    saved_models_path = os_module.path.join(os_module.path.dirname(__file__), "..", "saved_models")
    mappings_csv_path = os_module.path.join(os_module.path.dirname(__file__), "..", "mapcsv", "mappings.csv")
    fallacies_json_path = os_module.path.join(os_module.path.dirname(__file__), "..", "public", "data", "logicalfallacy.json")
    
    # List available models
    available_models = []
    if os_module.path.exists(saved_models_path):
        for item in os_module.listdir(saved_models_path):
            item_path = os_module.path.join(saved_models_path, item)
            if os_module.path.isdir(item_path):
                available_models.append(item)
    
    return jsonify({
        "status": "operational",
        "paths": {
            "saved_models": saved_models_path,
            "saved_models_exists": os_module.path.exists(saved_models_path),
            "mappings_csv": mappings_csv_path,
            "mappings_csv_exists": os_module.path.exists(mappings_csv_path),
            "fallacies_json": fallacies_json_path,
            "fallacies_json_exists": os_module.path.exists(fallacies_json_path)
        },
        "available_models": available_models,
        "default_model": "electra-logic",
        "message": "Local fallacy classification is ready. Use /api/classify_fallacy endpoint."
    })


# ==============================
# Run App
# ==============================
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 COGNIX - Unified Reasoning Assistant")
    print("=" * 60)
    print(f"📦 LLM Model: {llm_client.model}")
    print(f"🔬 Local Model: saved_models/electra-logic")
    print(f"🔗 Unified Backend: Chatbot + Extension use same logic")
    print(f"📊 Local Fallacy Detection: ENABLED (no LLM for fallacies)")
    print(f"🌐 Server: http://localhost:5001")
    print("=" * 60)
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5001)
