"""
Configuration for the Enterprise AI System.
All settings centralized here for easy tuning.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
JWT_SECRET = os.getenv("JWT_SECRET", "demo-secret-key-for-testing")
USE_REAL_LLM = bool(OPENAI_API_KEY and OPENAI_API_KEY != "your-key-here")

# --- Model Settings ---
MODELS = {
    "simple": {"name": "gpt-3.5-turbo", "temperature": 0.1, "max_tokens": 256},
    "medium": {"name": "gpt-4", "temperature": 0.3, "max_tokens": 1024},
    "complex": {"name": "gpt-4", "temperature": 0.4, "max_tokens": 2048},
}

# --- Cost per 1K tokens (USD) ---
MODEL_COSTS = {
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "gpt-4": {"input": 0.03, "output": 0.06},
}

# --- Rate Limits ---
RATE_LIMITS = {
    "requests_per_minute": 10,
    "tokens_per_minute": 50000,
}

# --- Cost Budgets ---
BUDGETS = {
    "per_request_max": 0.10,  # USD
    "per_user_daily": 1.00,   # USD
    "system_daily": 50.00,    # USD
}

# --- Guardrail Thresholds ---
GUARDRAILS = {
    "injection_score_threshold": 0.7,
    "pii_block": True,
    "max_input_length": 5000,
    "max_output_length": 10000,
}

# --- Evaluation ---
EVALUATION = {
    "confidence_threshold": 0.4,  # Below this → abstain
    "faithfulness_threshold": 0.5,
}

# --- Routing Keywords ---
ROUTING = {
    "complex_keywords": [
        "compare", "analyze", "explain the trend", "step by step",
        "differences between", "summarize all", "pros and cons",
        "recommend", "evaluate"
    ],
    "simple_keywords": [
        "what is", "define", "hello", "hi", "thanks",
        "how are you", "calculate"
    ],
    "simple_max_length": 50,
    "complex_min_length": 80,
}

# --- Prompt Templates ---
PROMPTS = {
    "system_rag": (
        "You are a helpful assistant for NovaTech Inc. "
        "Answer questions based ONLY on the provided context. "
        "If the context doesn't contain the answer, say so. "
        "Always cite your sources."
    ),
    "system_simple": (
        "You are a helpful assistant. Answer concisely and accurately."
    ),
    "system_agent": (
        "You are an analytical assistant. Break complex questions into steps, "
        "use available tools, and synthesize comprehensive answers with evidence."
    ),
}

# --- Feature Flags ---
FEATURES = {
    "guardrails_enabled": True,
    "cost_tracking_enabled": True,
    "memory_enabled": True,
    "observability_enabled": True,
    "cascade_on_failure": True,
}
