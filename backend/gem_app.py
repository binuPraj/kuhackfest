from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from dotenv import load_dotenv
import requests

# ==============================
# Load environment variables
# ==============================
load_dotenv()

app = Flask(__name__)
CORS(app)

# ==============================
# OpenRouter Configuration
# ==============================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = "google/gemma-3-27b-it:free"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

if not OPENROUTER_API_KEY:
    print("❌ OPENROUTER_API_KEY not found in environment variables")

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "http://localhost:5000",
    "X-Title": "Argument Analysis API"
}

# ==============================
# Load Prompt Templates
# ==============================
TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), "templates.json")
DB_PATH = os.path.join(os.path.dirname(__file__), "../public/data/db.json")

try:
    with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
        templates = json.load(f)
except FileNotFoundError:
    print("❌ templates.json not found")
    templates = {}

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

# ==============================
# OpenRouter LLM Call
# ==============================
def llm_completion(system_role, prompt):
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_role},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt + "\n\nReturn ONLY valid JSON. No explanation. No markdown."
                    }
                ]
            }
        ],
        "temperature": 0.7
    }#Temperature controls randomness in the model’s output.High temperature → allow riskier choices

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers=HEADERS,
            data=json.dumps(payload),
            timeout=60
        )
         # Your code sends an HTTP POST request to OpenRouter
# OpenRouter reads "model": "google/gemma-3-27b-it:free" from your payload
# OpenRouter routes your request to the Gemma model
# Gemma processes your prompt and generates a response
# Response flows back: Gemma → OpenRouter → Your code

        if response.status_code != 200:
            print("❌ OpenRouter error:", response.text)
            return None

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return clean_json_response(content)#cleaned gives you text (a string) that follows JSON rules.

    except Exception as e:
        print("❌ OpenRouter exception:", e)
        return None

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
    data = request.get_json(force=True)
    argument_text = data.get("argument_text")

    if not argument_text:
        return jsonify({"error": "Missing argument_text"}), 400

    template = templates.get("extract_toulmin")#templates. holds. thedict. from. the. templates. .json,gets. the. value. of. the. key
    if not template:
        return jsonify({"error": "Template not found"}), 500

    prompt = template["prompt"].replace("{{ARGUMENT_TEXT}}", argument_text)#Build the prompt dynamically

    result = llm_completion(template["role"], prompt)
    if result is None:
        return jsonify({"error": "LLM failed"}), 500

    try:
        return jsonify(json.loads(result))#loads=. str. to. dict. json. format,jsonify. ,prepares. to. http. response
    except json.JSONDecodeError:
        return jsonify({"raw_response": result})
# Your code sends an HTTP POST request to OpenRouter
# OpenRouter reads "model": "google/gemma-3-27b-it:free" from your payload
# OpenRouter routes your request to the Gemma model
# Gemma processes your prompt and generates a response
# Response flows back: Gemma → OpenRouter → Your code

@app.route("/api/support_mode", methods=["POST"])
def support_mode():#notcalledanywhere
    data = request.get_json(force=True)
    argument_text = data.get("argument_text")
    fallacy_type = data.get("fallacy_type")

    if not argument_text or not fallacy_type:
        return jsonify({"error": "Missing argument_text or fallacy_type"}), 400

    template = templates.get("support_mode")#templates. holds. thedict. from. the. templates. .json
    if not template:
        return jsonify({"error": "Template not found"}), 500

    prompt = (
        template["prompt"]
        .replace("{{ARGUMENT_TEXT}}", argument_text)
        .replace("{{FALLACY_TYPE}}", fallacy_type)
    )

    result = llm_completion(template["role"], prompt)
    if result is None:
        return jsonify({"error": "LLM failed"}), 500

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
        return jsonify({"error": "LLM failed"}), 500

    return jsonify({"response": result})

@app.route("/api/evaluate_user_response", methods=["POST"])
def evaluate_user_response():#notcalledanywhere
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
        print(f"❌ Error reading chat history: {e}")
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
            first_arg_text = new_entry.get("raw_text", "")#rae text is the user input argument 
            title = generate_chat_title(first_arg_text)
            
            new_chat_id = "chat_" + str(os.urandom(4).hex())
            target_chat = {
                "chat_id": new_chat_id,
                "title": title,
                "created_at": new_entry.get("timestamp"),
                "arguments": []
            }
            # Prepend to list so it shows at top
            db_data["chats"].insert(0, target_chat)#inserting. new chat in db
            
        # Add the new argument/interaction
        target_chat["arguments"].append(new_entry) #inserting argumen in target chat,as this dict are mutable it is already pointing to the chat in db_data as target_chat=chat (same loc pointed by both )
        
        # Recalculate global insights with the new data
        db_data = recalculate_insights(db_data)
        
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(db_data, f, indent=2)#so when it saves it also saves the new argument in the chat in db_data
            
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
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5001)
