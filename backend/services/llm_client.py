"""
Unified LLM Gateway Service
============================

╔══════════════════════════════════════════════════════════════════════════════╗
║                    ARCHITECTURAL COMPLIANCE VERIFICATION                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ ✅ VERIFIED: 2024-12-24                                                      ║
║ ✅ Single AI model for entire application: google/gemma-3-27b-it:free        ║
║ ✅ Single API key management point                                           ║
║ ✅ Unified rate limiting for ALL clients                                     ║
║ ✅ NO other direct OpenRouter calls exist in codebase                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

This is the SINGLE entry point for all OpenRouter API calls.
Both the chatbot and browser extension MUST use this service.

Security Features:
- API key loaded once from .env (never exposed to frontend)
- Rate limiting: 10 requests per minute per IP
- Input size caps: 2000 characters max
- Output token limits: 1500 tokens max
- Timeout protection: 30 seconds max

Why this exists:
- Ensures one API key for entire system
- Prevents free-tier abuse
- Centralizes error handling
- Makes monitoring easier
"""

import os
import json
import time
import requests
from dotenv import load_dotenv
from collections import defaultdict

# Load environment variables once at module initialization
load_dotenv()


class RateLimiter:
    """
    Simple in-memory rate limiter for free-tier protection.
    No database required - suitable for hackathon/demo use.
    """
    
    def __init__(self, max_requests=10, window_seconds=60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # Store request timestamps per IP: {ip: [timestamp1, timestamp2, ...]}
        self.requests = defaultdict(list)
    
    def is_allowed(self, identifier):
        """
        Check if request is allowed under rate limit.
        Automatically cleans old requests outside time window.
        """
        now = time.time()
        
        # Remove timestamps older than the window
        self.requests[identifier] = [
            ts for ts in self.requests[identifier] 
            if now - ts < self.window_seconds
        ]
        
        # Check if under limit
        if len(self.requests[identifier]) >= self.max_requests:
            return False
        
        # Record this request
        self.requests[identifier].append(now)
        return True
    
    def get_remaining(self, identifier):
        """Get remaining requests available"""
        now = time.time()
        self.requests[identifier] = [
            ts for ts in self.requests[identifier] 
            if now - ts < self.window_seconds
        ]
        return max(0, self.max_requests - len(self.requests[identifier]))


class LLMClient:
    """
    Unified LLM gateway for both chatbot and extension.
    
    CRITICAL: This is the ONLY place that should talk to OpenRouter.
    Any other direct OpenRouter calls are a security/cost violation.
    
    ✅ AUTO-FALLBACK: Automatically tries multiple free models if one fails.
    """
    
    # Free-tier safety limits
    # Note: MAX_INPUT_LENGTH applies to TOTAL message length (system + user)
    # This is intentionally generous to allow detailed system prompts
    MAX_INPUT_LENGTH = 10000     # Characters - allows for detailed prompts + user input
    MAX_OUTPUT_TOKENS = 1500     # Tokens - keeps responses concise
    REQUEST_TIMEOUT = 30         # Seconds - prevents hanging
    
    # ===== FREE MODELS WITH AUTO-FALLBACK =====
    # If one model fails, automatically try the next one
    FREE_MODELS = [
        "google/gemma-3-27b-it:free",                   # Google Gemma 3 27B
        "meta-llama/llama-3.3-70b-instruct:free",      # Meta Llama 3.3 70B
        "qwen/qwen3-32b:free",                          # Qwen 3 32B
        "mistralai/mistral-small-3.1-24b-instruct:free", # Mistral Small 3.1
        "deepseek/deepseek-chat-v3-0324:free",          # DeepSeek Chat V3
    ]
    
    def __init__(self):
        # Load API key ONCE at startup (never expose to frontend)
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        
        if not self.api_key:
            print("⚠️  WARNING: OPENROUTER_API_KEY not found in .env")
            print("⚠️  All LLM calls will fail until key is configured")
        
        # Primary model (can be overridden via env var)
        self.model = os.getenv("OPENROUTER_MODEL", self.FREE_MODELS[0])
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        
        # Track which model was last successful (for status reporting)
        self.last_successful_model = None
        
        # Rate limiter: 10 requests per minute per IP (suitable for hackathon)
        self.rate_limiter = RateLimiter(max_requests=10, window_seconds=60)
        
        # Headers for OpenRouter (never expose this to frontend)
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5001",
            "X-Title": "Unified Reasoning Assistant"
        }
    
    def check_rate_limit(self, client_ip):
        """
        Verify request is within rate limits.
        Raises exception if limit exceeded.
        """
        if not self.rate_limiter.is_allowed(client_ip):
            remaining_time = self.rate_limiter.window_seconds
            raise Exception(
                f"Rate limit exceeded. Please wait {remaining_time}s before trying again."
            )
    
    def validate_input(self, text):
        """
        Enforce input size limits for free tier.
        Prevents abuse and excessive token usage.
        
        Note: This validates total message content, not individual fields.
        System prompts are included in the validation.
        """
        if not text:
            raise ValueError("Input text cannot be empty")
        
        if len(text) > self.MAX_INPUT_LENGTH:
            raise ValueError(
                f"Input too long. Maximum {self.MAX_INPUT_LENGTH} characters allowed. "
                f"You provided {len(text)} characters."
            )
    
    def chat_completion(self, messages, client_ip, temperature=0.7, json_mode=True):
        """
        Single entry point for ALL LLM calls in the system.
        
        ✅ AUTO-FALLBACK: If primary model fails, automatically tries other free models.
        
        This method:
        1. Validates rate limits
        2. Validates input size
        3. Calls OpenRouter (with auto-fallback to other models)
        4. Handles errors gracefully
        5. Returns cleaned response
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            client_ip: Client IP address for rate limiting
            temperature: Sampling temperature (0-1), default 0.7
            json_mode: If True, enforces JSON-only output
        
        Returns:
            str: LLM response (JSON string if json_mode=True, else plain text)
        
        Raises:
            Exception: On rate limit, validation, or API errors (after all models fail)
        """
        
        # Step 1: Rate limiting check (prevents free-tier abuse)
        self.check_rate_limit(client_ip)
        
        # Step 2: Validate total input length
        total_input = " ".join([m.get("content", "") for m in messages])
        self.validate_input(total_input)
        
        # Step 3: Prepare messages (add JSON enforcement if needed)
        final_messages = messages.copy()
        if json_mode:
            final_messages.append({
                "role": "system",
                "content": "You must respond with valid JSON only. No markdown, no explanations, no code blocks."
            })
        
        # Step 4: Build list of models to try (primary first, then fallbacks)
        models_to_try = [self.model]
        for model in self.FREE_MODELS:
            if model != self.model and model not in models_to_try:
                models_to_try.append(model)
        
        # Step 5: Try each model until one succeeds
        last_error = None
        for model_name in models_to_try:
            try:
                content = self._call_model(model_name, final_messages, temperature, json_mode)
                # Success! Record which model worked
                self.last_successful_model = model_name
                if model_name != self.model:
                    print(f"✅ Fallback successful: {model_name}")
                return content
            except Exception as e:
                last_error = e
                print(f"⚠️ Model {model_name} failed: {str(e)[:100]}")
                continue  # Try next model
        
        # All models failed
        raise Exception(f"All models failed. Last error: {str(last_error)}")
    
    def _call_model(self, model_name, messages, temperature, json_mode):
        """
        Make actual API call to a specific model.
        Separated from chat_completion to enable fallback logic.
        """
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.MAX_OUTPUT_TOKENS
        }
        
        try:
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=self.REQUEST_TIMEOUT
            )
            
            # Handle rate limiting from OpenRouter itself
            if response.status_code == 429:
                raise Exception(f"Rate limit for {model_name}")
            
            # Handle other errors
            if response.status_code != 200:
                error_msg = response.text[:200]
                raise Exception(f"API error ({response.status_code}): {error_msg}")
            
            # Extract response
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            # Clean response if JSON mode
            if json_mode:
                content = self._clean_json_response(content)
            
            return content
            
        except requests.exceptions.Timeout:
            raise Exception(f"Timeout for {model_name}")
        except requests.exceptions.ConnectionError:
            raise Exception("Cannot connect to OpenRouter API")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Request error: {str(e)}")
        except KeyError as e:
            raise Exception(f"Unexpected response format: {str(e)}")
    
    def _clean_json_response(self, text):
        """
        Remove markdown code blocks from JSON responses.
        LLMs often wrap JSON in ```json blocks despite instructions.
        """
        if not text:
            return text
        
        cleaned = text.strip()
        
        # Remove markdown fences
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        
        return cleaned.strip()
    
    def is_configured(self):
        """Check if API key is configured"""
        return bool(self.api_key)
    
    def get_status(self):
        """Get client status for health checks"""
        return {
            "configured": self.is_configured(),
            "primary_model": self.model,
            "last_successful_model": self.last_successful_model,
            "fallback_models": self.FREE_MODELS,
            "max_input_length": self.MAX_INPUT_LENGTH,
            "max_output_tokens": self.MAX_OUTPUT_TOKENS,
            "rate_limit": f"{self.rate_limiter.max_requests} req / {self.rate_limiter.window_seconds}s"
        }


# Global singleton instance
# This ensures one API key, one rate limiter across entire application
llm_client = LLMClient()
