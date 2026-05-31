"""
Model Router - Intelligent Request Routing

Classifies request complexity and routes to the optimal model.
Demonstrates cascade pattern and cost savings tracking.
"""

import os
import re
from dataclasses import dataclass, field
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI()

# --- Configuration ---

MODEL_PRICING = {
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.005, "output": 0.015},
}

ROUTING_MAP = {
    "simple": "gpt-3.5-turbo",
    "medium": "gpt-4o-mini",
    "complex": "gpt-4o",
}

# The most expensive model (baseline for savings calculation)
BASELINE_MODEL = "gpt-4o"


# --- Complexity Classifier ---

# Keywords suggesting complexity
COMPLEX_KEYWORDS = [
    "analyze", "architect", "design", "compare and contrast",
    "implement", "optimize", "debug", "refactor", "explain in detail",
    "step by step", "tradeoffs", "pros and cons", "distributed",
    "algorithm", "system design", "security implications",
]

SIMPLE_KEYWORDS = [
    "hello", "hi", "thanks", "bye", "what is", "define",
    "who is", "when was", "where is", "yes", "no",
    "translate", "convert", "capital of",
]


def classify_complexity(message: str) -> str:
    """
    Classify the complexity of a request using heuristics.
    
    Returns: "simple", "medium", or "complex"
    """
    message_lower = message.lower().strip()
    word_count = len(message.split())
    
    # --- Fast path: obvious simple queries ---
    if word_count < 5:
        return "simple"
    
    if any(kw in message_lower for kw in SIMPLE_KEYWORDS) and word_count < 15:
        return "simple"
    
    # --- Signals of complexity ---
    signals = []
    
    # Length signals
    if word_count > 100:
        signals.append("long_input")
    if word_count > 50:
        signals.append("moderate_length")
    
    # Content signals
    if "```" in message:
        signals.append("has_code")
    if message.count("?") > 2:
        signals.append("multi_question")
    if any(kw in message_lower for kw in COMPLEX_KEYWORDS):
        signals.append("complex_keywords")
    if re.search(r'\d+\.\s', message):
        signals.append("numbered_list")  # Multi-part request
    if any(word in message_lower for word in ["but", "however", "although", "whereas"]):
        signals.append("nuanced_reasoning")
    
    # Domain signals
    if any(term in message_lower for term in ["api", "database", "kubernetes", "terraform"]):
        signals.append("technical_domain")
    
    # --- Classify based on signal count ---
    complexity_score = len(signals)
    
    if complexity_score >= 3:
        return "complex"
    elif complexity_score >= 1:
        return "medium"
    else:
        return "simple"


# --- Router ---

@dataclass
class RoutingDecision:
    query: str
    complexity: str
    model_used: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    baseline_cost: float = 0.0
    savings_pct: float = 0.0
    response: str = ""
    cascade_escalated: bool = False


@dataclass
class RouterStats:
    total_requests: int = 0
    total_cost: float = 0.0
    total_baseline_cost: float = 0.0
    decisions: list = field(default_factory=list)
    
    @property
    def total_savings_pct(self) -> float:
        if self.total_baseline_cost == 0:
            return 0
        return (1 - self.total_cost / self.total_baseline_cost) * 100


stats = RouterStats()


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_PRICING[model]
    return (input_tokens / 1000) * pricing["input"] + \
           (output_tokens / 1000) * pricing["output"]


def route_request(message: str, use_cascade: bool = False) -> RoutingDecision:
    """
    Route a request to the optimal model.
    
    If use_cascade=True, tries cheap model first and escalates if response
    seems low quality (short, contains hedge words).
    """
    complexity = classify_complexity(message)
    model = ROUTING_MAP[complexity]
    escalated = False
    
    if use_cascade and complexity != "complex":
        # Try the cheaper model first
        cheap_model = ROUTING_MAP["simple"]
        response = client.chat.completions.create(
            model=cheap_model,
            messages=[{"role": "user", "content": message}],
            max_tokens=500,
        )
        
        answer = response.choices[0].message.content
        
        # Check confidence heuristics
        low_confidence = (
            len(answer.split()) < 10 or
            any(phrase in answer.lower() for phrase in [
                "i'm not sure", "i don't know", "it depends",
                "i cannot", "as an ai", "i'm unable"
            ])
        )
        
        if low_confidence and complexity != "simple":
            # Escalate to the originally classified model
            escalated = True
            # Fall through to use the classified model below
        else:
            # Cheap model worked fine
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            cost = calculate_cost(cheap_model, input_tokens, output_tokens)
            baseline_cost = calculate_cost(BASELINE_MODEL, input_tokens, output_tokens)
            
            decision = RoutingDecision(
                query=message[:80],
                complexity=complexity,
                model_used=cheap_model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                baseline_cost=baseline_cost,
                savings_pct=(1 - cost / baseline_cost) * 100 if baseline_cost > 0 else 0,
                response=answer,
                cascade_escalated=False,
            )
            _track(decision)
            return decision
    
    # Standard routing (or cascade escalation)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": message}],
        max_tokens=500,
    )
    
    answer = response.choices[0].message.content
    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens
    cost = calculate_cost(model, input_tokens, output_tokens)
    baseline_cost = calculate_cost(BASELINE_MODEL, input_tokens, output_tokens)
    
    decision = RoutingDecision(
        query=message[:80],
        complexity=complexity,
        model_used=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=cost,
        baseline_cost=baseline_cost,
        savings_pct=(1 - cost / baseline_cost) * 100 if baseline_cost > 0 else 0,
        response=answer,
        cascade_escalated=escalated,
    )
    _track(decision)
    return decision


def _track(decision: RoutingDecision):
    stats.total_requests += 1
    stats.total_cost += decision.cost
    stats.total_baseline_cost += decision.baseline_cost
    stats.decisions.append(decision)


def print_decision(d: RoutingDecision):
    print(f"\n{'='*60}")
    print(f"Query: {d.query}...")
    print(f"Classification: {d.complexity.upper()}")
    print(f"Routed to: {d.model_used}")
    if d.cascade_escalated:
        print(f"  (escalated via cascade)")
    print(f"Tokens: {d.input_tokens} in / {d.output_tokens} out")
    print(f"Cost: ${d.cost:.6f}")
    print(f"Baseline (GPT-4o): ${d.baseline_cost:.6f}")
    print(f"Savings: {d.savings_pct:.1f}%")
    print(f"Response: {d.response[:150]}...")


def print_summary():
    print(f"\n{'='*60}")
    print("ROUTING SUMMARY")
    print(f"{'='*60}")
    print(f"Total requests: {stats.total_requests}")
    print(f"Total cost: ${stats.total_cost:.6f}")
    print(f"Baseline cost (all GPT-4o): ${stats.total_baseline_cost:.6f}")
    print(f"Total savings: {stats.total_savings_pct:.1f}%")
    print(f"Money saved: ${stats.total_baseline_cost - stats.total_cost:.6f}")


# --- Demo ---

if __name__ == "__main__":
    test_queries = [
        # Simple
        "What is the capital of France?",
        "Hello, how are you?",
        "Define photosynthesis.",
        
        # Medium
        "Explain the differences between REST and GraphQL APIs, including when to use each.",
        "Write a Python function that implements binary search with error handling.",
        
        # Complex
        "Design a distributed system for real-time fraud detection that handles 1 million transactions per second. Consider consistency, availability, and partition tolerance tradeoffs.",
        "Analyze the security implications of using JWT tokens vs session cookies in a microservices architecture with multiple trust boundaries.",
    ]
    
    print("MODEL ROUTER - Intelligent Request Routing Demo")
    print("=" * 60)
    print(f"Routing: simple→gpt-3.5-turbo, medium→gpt-4o-mini, complex→gpt-4o")
    print(f"Cascade mode: enabled (try cheap first, escalate if needed)")
    
    for query in test_queries:
        decision = route_request(query, use_cascade=True)
        print_decision(decision)
    
    print_summary()
