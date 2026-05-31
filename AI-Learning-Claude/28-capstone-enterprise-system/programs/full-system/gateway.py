"""
AI Gateway.
Central hub: rate limiting, cost checking, request routing, fallback.
"""

import time
from config import RATE_LIMITS, FEATURES
from router import route_query
from guardrails import check_input_guardrails, check_output_guardrails
from cost_tracker import cost_tracker
from memory import memory
from observability import Trace


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self):
        self.requests: dict[str, list[float]] = {}  # user_id → timestamps

    def check(self, user_id: str) -> tuple[bool, int]:
        """Check rate limit. Returns (allowed, retry_after_seconds)."""
        now = time.time()
        window = 60  # 1 minute window

        if user_id not in self.requests:
            self.requests[user_id] = []

        # Clean old entries
        self.requests[user_id] = [t for t in self.requests[user_id] if now - t < window]

        if len(self.requests[user_id]) >= RATE_LIMITS["requests_per_minute"]:
            oldest = self.requests[user_id][0]
            retry_after = int(window - (now - oldest)) + 1
            print(f"[GATEWAY] Rate limit EXCEEDED for user={user_id} ({len(self.requests[user_id])}/{RATE_LIMITS['requests_per_minute']})")
            return False, retry_after

        self.requests[user_id].append(now)
        return True, 0


rate_limiter = RateLimiter()


def process_request(query: str, user_context: dict, session_id: str, trace: Trace) -> dict:
    """
    Main gateway function. Orchestrates the full request lifecycle.
    """
    user_id = user_context["user_id"]
    print(f"\n[GATEWAY] Processing request from user={user_id}")
    print(f"[GATEWAY] Query: \"{query[:80]}{'...' if len(query) > 80 else ''}\"")

    # Step 1: Rate limiting
    span = trace.start_span("rate_limit_check")
    allowed, retry_after = rate_limiter.check(user_id)
    span.end()
    if not allowed:
        return {
            "error": "Rate limit exceeded",
            "retry_after_seconds": retry_after,
            "status": "rate_limited",
        }

    # Step 2: Budget check
    span = trace.start_span("budget_check")
    budget_ok, budget_msg = cost_tracker.check_budget(user_id)
    span.end()
    if not budget_ok:
        return {"error": budget_msg, "status": "budget_exceeded"}

    # Step 3: Input guardrails
    if FEATURES["guardrails_enabled"]:
        span = trace.start_span("input_guardrails")
        guard_result = check_input_guardrails(query)
        span.end(result=str(guard_result))
        if not guard_result.passed:
            trace.add_metric("route", "blocked")
            return {
                "answer": "I'm unable to process this request. " + guard_result.reason,
                "status": "blocked",
                "reason": guard_result.reason,
                "route": "blocked",
            }

    # Step 4: Memory context
    memory_context = ""
    if FEATURES["memory_enabled"]:
        span = trace.start_span("memory_lookup")
        memory_context = memory.get_context_for_query(session_id, user_id)
        # Extract and store any preferences
        prefs = memory.extract_preferences(query)
        for key, value in prefs.items():
            memory.store_preference(user_id, key, value)
        span.end()

    # Step 5: Route and process
    span = trace.start_span("routing_and_processing")
    result = route_query(query, user_context, session_id)
    span.end(route=result.get("route", "unknown"))

    # Step 6: Output guardrails
    if FEATURES["guardrails_enabled"] and "answer" in result:
        span = trace.start_span("output_guardrails")
        output_guard = check_output_guardrails(result["answer"])
        span.end(result=str(output_guard))
        if not output_guard.passed:
            result["answer"] = "[Response filtered by safety guardrails]"
            result["filtered"] = True

    # Step 7: Track cost
    if FEATURES["cost_tracking_enabled"] and "tokens" in result:
        span = trace.start_span("cost_tracking")
        model = result.get("model", "gpt-3.5-turbo")
        tokens = result["tokens"]
        cost = cost_tracker.record_cost(user_id, model, tokens["input"], tokens["output"])
        result["cost"] = cost
        trace.add_metric("cost", cost)
        span.end(cost=cost)

    # Step 8: Store in memory
    if FEATURES["memory_enabled"]:
        memory.store_message(session_id, "user", query)
        if "answer" in result:
            memory.store_message(session_id, "assistant", result["answer"])

    # Record metrics on trace
    trace.add_metric("route", result.get("route", "unknown"))
    trace.add_metric("confidence", result.get("confidence", 0))
    trace.add_metric("model", result.get("model", "unknown"))
    if "tokens" in result:
        trace.add_metric("tokens_total", result["tokens"]["input"] + result["tokens"]["output"])

    result["status"] = "success"
    result["trace_id"] = trace.trace_id
    return result
