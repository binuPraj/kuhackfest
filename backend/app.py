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
OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

if not OPENROUTER_API_KEY:
    print("❌ OPENROUTER_API_KEY not found in environment variables")

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    # Optional but recommended
    "HTTP-Referer": "http://localhost:5000",
    "X-Title": "Argument Analysis API"
}

# ==============================
# Load Prompt Templates
# ==============================

TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), "templates.json")

try:
    with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
        templates = json.load(f)
except FileNotFoundError:
    print("❌ templates.json not found")
    templates = {}

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
                "content": prompt
                + "\n\nReturn ONLY valid JSON. No explanation. No markdown."
            }
        ],
        "temperature": 0.7,
    }

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers=HEADERS,
            data=json.dumps(payload),
            timeout=60
        )

        if response.status_code != 200:
            print("❌ OpenRouter error:", response.text)
            return None

        data = response.json()
        return data["choices"][0]["message"]["content"]

    except Exception as e:
        print("❌ OpenRouter exception:", e)
        return None

# ==============================
# API ROUTES
# ==============================

@app.route("/api/extract_toulmin", methods=["POST"])
def extract_toulmin():
    data = request.get_json(force=True)
    argument_text = data.get("argument_text")

    if not argument_text:
        return jsonify({"error": "Missing argument_text"}), 400

    template = templates.get("extract_toulmin")
    if not template:
        return jsonify({"error": "Template not found"}), 500

    prompt = template["prompt"].replace("{{ARGUMENT_TEXT}}", argument_text)

    result = llm_completion(template["role"], prompt)
    if result is None:
        return jsonify({"error": "LLM failed"}), 500

    try:
        return jsonify(json.loads(result))
    except json.JSONDecodeError:
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


# ==============================
# Run App
# ==============================

if __name__ == "__main__":
    app.run(debug=True, port=5000)
