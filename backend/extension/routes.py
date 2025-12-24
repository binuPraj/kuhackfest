import os
import time
from collections import defaultdict, deque
from functools import wraps
from typing import Any, Dict, Tuple

from flask import Blueprint, jsonify, request

from . import ai_client, prompts, reasoning


bp = Blueprint("extension_api", __name__)

RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW_MS", "60000")) / 1000.0
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "15"))
_request_log: Dict[str, deque] = defaultdict(deque)


def rate_limited(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        ip = request.remote_addr or "unknown"
        now = time.time()
        window_start = now - RATE_LIMIT_WINDOW
        bucket = _request_log[ip]

        while bucket and bucket[0] < window_start:
            bucket.popleft()

        if len(bucket) >= RATE_LIMIT_MAX_REQUESTS:
            return jsonify({"error": "Too many requests, please try again later."}), 429

        bucket.append(now)
        return fn(*args, **kwargs)

    return wrapper


def _parse_json_body() -> Tuple[Dict[str, Any], int]:
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return {}, 400
    return body, 200


def _validate_text_field(text: Any, field_name: str = "text") -> Tuple[str, Dict[str, Any]]:
    if not isinstance(text, str):
        return "", {
            "error": "Invalid request",
            "message": f"{field_name} is required and must be a string",
        }
    if len(text) < 10:
        return "", {"error": "Text too short", "message": f"{field_name} must be at least 10 characters long"}
    if len(text) > 5000:
        return "", {"error": "Text too long", "message": f"{field_name} must not exceed 5000 characters"}
    return text.strip(), {}


def _json_or_fallback(content: Any, fallback_key: str) -> Dict[str, Any]:
    try:
        return content if isinstance(content, dict) else prompts.FALLBACK_RESPONSES[fallback_key]
    except Exception:
        return prompts.FALLBACK_RESPONSES[fallback_key]


@bp.route("/analyze", methods=["POST"])
@rate_limited
def analyze_text():
    body, status = _parse_json_body()
    if status != 200:
        return jsonify({"error": "Invalid JSON body"}), 400

    text, error = _validate_text_field(body.get("text"))
    if error:
        return jsonify(error), 400

    context = body.get("context") or {}
    if context and not isinstance(context, dict):
        return jsonify({"error": "Invalid context", "message": "context must be an object"}), 400

    try:
        system_prompt = prompts.get_analysis_system_prompt()
        user_prompt = prompts.generate_analysis_prompt(text, context)
        result = ai_client.call_ai(
            system_prompt,
            user_prompt,
            {"jsonMode": True, "temperature": 0.7, "max_tokens": 1500},
        )
        enriched = reasoning.enrich_analysis_result(result)

        if not enriched.get("fallacies"):
            enriched["fallacies"] = []
        if not enriched.get("suggestions"):
            enriched["suggestions"] = []
        if not enriched.get("toulminAnalysis"):
            enriched["toulminAnalysis"] = reasoning.create_empty_toulmin_analysis()

        enriched["issues"] = [
            {
                "type": fallacy.get("type"),
                "severity": fallacy.get("severity", "warning"),
                "description": fallacy.get("description") or fallacy.get("explanation"),
                "example": fallacy.get("excerpt"),
            }
            for fallacy in enriched.get("fallacies", [])
        ]

        return jsonify(enriched)
    except Exception as exc:
        print(f"❌ Error in /api/analyze: {exc}")
        return jsonify(prompts.FALLBACK_RESPONSES["analysis"])


@bp.route("/detect-fallacies", methods=["POST"])
@rate_limited
def detect_fallacies():
    body, status = _parse_json_body()
    if status != 200:
        return jsonify({"error": "Invalid JSON body"}), 400

    text, error = _validate_text_field(body.get("text"))
    if error:
        return jsonify(error), 400

    try:
        system_prompt = prompts.get_fallacy_detection_system_prompt()
        user_prompt = prompts.generate_fallacy_prompt(text)
        result = ai_client.call_ai(
            system_prompt,
            user_prompt,
            {"jsonMode": True, "temperature": 0.6, "max_tokens": 1000},
        )

        fallacies = result.get("fallacies") if isinstance(result, dict) else None
        if not fallacies or not isinstance(fallacies, list):
            fallacies = []

        enriched_fallacies = [reasoning.enrich_fallacy_data(f) for f in fallacies]
        base = result if isinstance(result, dict) else {}
        response_body = dict(base)
        response_body["fallacies"] = enriched_fallacies
        response_body["verifiedCount"] = len([f for f in enriched_fallacies if f.get("isVerified")])
        response_body["totalCount"] = len(enriched_fallacies)
        return jsonify(response_body)
    except Exception as exc:
        print(f"❌ Error in /api/detect-fallacies: {exc}")
        return jsonify(prompts.FALLBACK_RESPONSES["fallacies"])


@bp.route("/generate-reply", methods=["POST"])
@rate_limited
def generate_reply():
    body, status = _parse_json_body()
    if status != 200:
        return jsonify({"error": "Invalid JSON body"}), 400

    original_post, error = _validate_text_field(body.get("originalPost"), "originalPost")
    if error:
        return jsonify(error), 400

    draft_reply = body.get("draftReply")
    if draft_reply and not isinstance(draft_reply, str):
        return jsonify({"error": "Invalid draftReply", "message": "draftReply must be a string"}), 400

    tone = body.get("tone") or "neutral"
    if tone not in {"neutral", "polite", "assertive"}:
        return jsonify({"error": "Invalid tone", "message": "tone must be neutral, polite, or assertive"}), 400

    try:
        system_prompt = prompts.get_reply_generation_system_prompt()
        user_prompt = prompts.generate_reply_prompt(original_post, draft_reply or "", tone)
        result = ai_client.call_ai(
            system_prompt,
            user_prompt,
            {"jsonMode": True, "temperature": 0.8, "max_tokens": 1500},
        )

        replies = result.get("replies") if isinstance(result, dict) else None
        if not replies or not isinstance(replies, list):
            raise RuntimeError("Invalid AI response structure")

        return jsonify(result)
    except Exception as exc:
        print(f"❌ Error in /api/generate-reply: {exc}")
        return jsonify(prompts.FALLBACK_RESPONSES["reply"])


@bp.route("/rewrite", methods=["POST"])
@rate_limited
def rewrite_argument():
    body, status = _parse_json_body()
    if status != 200:
        return jsonify({"error": "Invalid JSON body"}), 400

    text, error = _validate_text_field(body.get("text"))
    if error:
        return jsonify(error), 400

    preserve_length = body.get("preserveLength", True)
    if not isinstance(preserve_length, bool):
        preserve_length = True

    try:
        system_prompt = prompts.get_rewrite_system_prompt()
        user_prompt = prompts.generate_rewrite_prompt(text, preserve_length)
        result = ai_client.call_ai(
            system_prompt,
            user_prompt,
            {"jsonMode": True, "temperature": 0.75, "max_tokens": 1500},
        )
        return jsonify(result if isinstance(result, dict) else prompts.FALLBACK_RESPONSES["rewrite"])
    except Exception as exc:
        print(f"❌ Error in /api/rewrite: {exc}")
        return jsonify(prompts.FALLBACK_RESPONSES["rewrite"])


@bp.route("/models", methods=["GET"])
@rate_limited
def get_models():
    context = reasoning.generate_analysis_context()
    return jsonify(
        {
            "status": "loaded",
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
        }
    )


@bp.route("/test", methods=["GET"])
@rate_limited
def test_connection():
    is_connected = ai_client.test_connection()
    provider_info = ai_client.get_provider_info()
    return jsonify(
        {
            "status": "connected" if is_connected else "disconnected",
            "message": "AI service is operational" if is_connected else "AI service connection failed",
            "provider": provider_info,
            "models": {
                "fallacies": len(reasoning.get_fallacy_definitions()),
                "toulminFactors": len(reasoning.get_toulmin_factors()),
            },
        }
    )


@bp.route("/health", methods=["GET"])
@rate_limited
def health():
    provider_info = ai_client.get_provider_info()
    return jsonify(
        {
            "status": "ok",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "version": "2.0.0",
            "provider": provider_info,
        }
    )
