# Services package - Shared business logic
# 
# This package provides unified services for both chatbot and extension:
# - llm_client: Unified AI gateway (Gemma model via OpenRouter)
# - core_service: Shared business logic (Toulmin analysis, fallacy detection)

from .llm_client import llm_client
from .core_service import (
    analyze_argument,
    improve_argument,
    generate_counter_argument,
    evaluate_response,
    generate_chat_title
)

__all__ = [
    "llm_client",
    "analyze_argument",
    "improve_argument", 
    "generate_counter_argument",
    "evaluate_response",
    "generate_chat_title"
]