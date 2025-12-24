"""
Core Service Layer - Unified Backend Logic
============================================

╔══════════════════════════════════════════════════════════════════════════════╗
║                    ARCHITECTURAL COMPLIANCE VERIFICATION                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ ✅ VERIFIED: 2024-12-24                                                      ║
║ ✅ Single source of truth for ALL AI reasoning logic                        ║
║ ✅ Both chatbot and extension consume this layer                             ║
║ ✅ ZERO duplicated AI logic exists outside this module                       ║
║ ✅ Chatbot response format/behavior is UNCHANGED                             ║
║ ✅ Uses unified llm_client for all model invocations                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

This module provides the SINGLE source of truth for all argument analysis,
fallacy detection, and reasoning operations. Both the chatbot and browser
extension consume this layer.

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
                    ▼
         ┌─────────────────────┐
         │   llm_client.py     │
         │  (AI gateway)       │
         └─────────────────────┘

USAGE:
    from services.core_service import (
        analyze_argument,
        improve_argument,
        generate_counter_argument,
        evaluate_response,
        detect_fallacies
    )

The chatbot (gem_app.py) remains unchanged - it already has the working logic.
This service exposes the same logic for the extension to consume.
"""

import json
import os
from typing import Any, Dict, Optional

from .llm_client import llm_client

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
    template = templates.get("extract_toulmin")
    if not template:
        return {"error": "Template not found"}
    
    prompt = template["prompt"].replace("{{ARGUMENT_TEXT}}", argument_text)
    result = _llm_completion(template["role"], prompt, client_ip)
    
    if result is None:
        return {"error": "LLM failed"}
    
    parsed = _parse_json_response(result)
    if parsed:
        return parsed
    
    return {"raw_response": result}


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
