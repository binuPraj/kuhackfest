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
    improve_argument,
    generate_counter_argument,
    evaluate_response,
    generate_chat_title
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
        "version": "2.0.0-unified",
        "status": "operational",
        "model": llm_client.model,
        "unified": True,
        "message": "Chatbot and Extension share the same backend logic",
        "endpoints": {
            "chatbot": {
                "extract_toulmin": "POST /api/extract_toulmin",
                "support_mode": "POST /api/support_mode",
                "oppose_mode": "POST /api/oppose_mode",
                "evaluate_user_response": "POST /api/evaluate_user_response",
                "get_chat_history": "GET /api/get_chat_history",
                "save_chat": "POST /api/save_chat"
            },
            "extension": {
                "analyze": "POST /api/analyze → Same logic as extract_toulmin",
                "detect_fallacies": "POST /api/detect-fallacies → Uses extract_toulmin",
                "generate_reply": "POST /api/generate-reply → Same logic as oppose_mode",
                "rewrite": "POST /api/rewrite → Same logic as support_mode",
                "models": "GET /api/models",
                "health": "GET /api/health",
                "test": "GET /api/test"
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
# Run App
# ==============================
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 COGNIX - Unified Reasoning Assistant")
    print("=" * 60)
    print(f"📦 Model: {llm_client.model}")
    print(f"🔗 Unified Backend: Chatbot + Extension use same logic")
    print(f"🌐 Server: http://localhost:5001")
    print("=" * 60)
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5001)
