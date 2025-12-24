"""
Extension AI Client - DEPRECATED
==================================

This module is now a thin wrapper around the unified LLM gateway.
All actual API calls go through services/llm_client.py

DO NOT add direct OpenRouter calls here.
DO NOT load API keys here.

Why: Ensures both chatbot and extension use same API key and rate limits.
"""

import json
import os
import re
from typing import Any, Dict, Optional
from flask import request

# Import unified LLM client (handles API key, rate limiting, etc.)
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.llm_client import llm_client


def _max_tokens(options: Dict[str, Any]) -> int:
    return int(options.get("max_tokens") or options.get("maxTokens") or 2000)



def parse_json_response(content: str) -> Dict[str, Any]:
    """Parse JSON from AI response, handling markdown code blocks"""
    if not content:
        raise ValueError("Empty response from AI provider")

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
    if fence_match:
        candidate = fence_match.group(1)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    object_match = re.search(r"\{[\s\S]*\}", content)
    if object_match:
        candidate = object_match.group(0)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise ValueError("AI returned invalid JSON")


def call_ai(system_prompt: str, user_prompt: str, options: Optional[Dict[str, Any]] = None) -> Any:
    """
    Main entry point for extension AI calls.
    
    NOW ROUTES THROUGH UNIFIED LLM CLIENT.
    This ensures:
    - Same API key as chatbot
    - Same rate limits
    - Consistent free-tier protection
    
    Args:
        system_prompt: System role/instructions
        user_prompt: User's actual prompt
        options: Dict with optional keys:
            - jsonMode: bool (default False)
            - temperature: float (default 0.7)
            - max_tokens: int (default 1500)
    
    Returns:
        Dict if jsonMode=True, str otherwise
    """
    options = options or {}
    
    # Check if unified client is configured
    if not llm_client.is_configured():
        raise RuntimeError("OpenRouter API key not configured in .env file")
    
    # Build messages array
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    # Get client IP for rate limiting
    # In request context, use request.remote_addr
    # Outside request context (tests), use localhost
    try:
        from flask import has_request_context
        if has_request_context():
            client_ip = request.remote_addr or "127.0.0.1"
        else:
            client_ip = "127.0.0.1"
    except:
        client_ip = "127.0.0.1"
    
    # Call unified LLM client (handles rate limiting, validation, etc.)
    try:
        response = llm_client.chat_completion(
            messages=messages,
            client_ip=client_ip,
            temperature=options.get("temperature", 0.7),
            json_mode=options.get("jsonMode", False)
        )
        
        # Parse JSON if requested
        if options.get("jsonMode"):
            return parse_json_response(response)
        
        return response
    
    except Exception as e:
        # Re-raise with context
        raise RuntimeError(f"LLM call failed: {str(e)}")


# DEPRECATED: Old provider-specific functions kept for compatibility
# These now redirect to unified client

def call_gemini(system_prompt: str, user_prompt: str, options: Dict[str, Any]) -> Any:
    """DEPRECATED: Use call_ai() instead - routes through unified client"""
    print("⚠️  call_gemini() is deprecated - use call_ai() which routes through unified client")
    return call_ai(system_prompt, user_prompt, options)


def call_openrouter(system_prompt: str, user_prompt: str, options: Dict[str, Any]) -> Any:
    """DEPRECATED: Use call_ai() instead - routes through unified client"""
    print("⚠️  call_openrouter() is deprecated - use call_ai() which routes through unified client")
    return call_ai(system_prompt, user_prompt, options)


def test_connection() -> bool:
    """Test if unified LLM client is working"""
    try:
        response = call_ai(
            "You are a helpful assistant.",
            "Respond with exactly: Connection successful",
            {"max_tokens": 50, "jsonMode": False},
        )
        if isinstance(response, str):
            return "connection successful" in response.lower()
        return False
    except Exception as e:
        print(f"Connection test failed: {e}")
        return False


def get_provider_info() -> Dict[str, Any]:
    """Get unified LLM client configuration info"""
    return llm_client.get_status()

    provider = AI_PROVIDER
    if provider in {"google", "gemini"}:
        return {"provider": "Google Gemini", "model": GOOGLE_MODEL, "isConfigured": bool(GOOGLE_API_KEY)}
    if provider == "openrouter":
        return {"provider": "OpenRouter", "model": OPENROUTER_MODEL, "isConfigured": bool(OPENROUTER_API_KEY)}
    return {"provider": "Google Gemini (default)", "model": GOOGLE_MODEL, "isConfigured": bool(GOOGLE_API_KEY)}
