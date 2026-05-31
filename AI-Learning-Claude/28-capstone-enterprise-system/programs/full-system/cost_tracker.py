"""
Cost Tracker module.
Per-request cost calculation, per-user aggregation, budget enforcement.
"""

import time
from config import MODEL_COSTS, BUDGETS


class CostTracker:
    """Tracks costs per request and per user with budget enforcement."""

    def __init__(self):
        self.user_daily_costs: dict[str, float] = {}  # user_id → daily total
        self.request_costs: list[dict] = []
        self.system_daily_cost: float = 0.0
        self.day_start: float = time.time()
        print("[COST] Cost tracker initialized")

    def _reset_if_new_day(self):
        """Reset daily counters if a new day has started."""
        if time.time() - self.day_start > 86400:
            self.user_daily_costs.clear()
            self.system_daily_cost = 0.0
            self.day_start = time.time()
            print("[COST] Daily counters reset")

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for a single request."""
        costs = MODEL_COSTS.get(model, {"input": 0.001, "output": 0.002})
        cost = (input_tokens / 1000) * costs["input"] + (output_tokens / 1000) * costs["output"]
        return round(cost, 6)

    def check_budget(self, user_id: str) -> tuple[bool, str]:
        """Check if user is within budget. Returns (allowed, reason)."""
        self._reset_if_new_day()

        user_cost = self.user_daily_costs.get(user_id, 0.0)
        if user_cost >= BUDGETS["per_user_daily"]:
            msg = f"Daily budget exceeded: used=${user_cost:.4f}, limit=${BUDGETS['per_user_daily']:.2f}"
            print(f"[COST] BUDGET EXCEEDED for user={user_id}: {msg}")
            return False, msg

        if self.system_daily_cost >= BUDGETS["system_daily"]:
            msg = f"System daily budget exceeded: ${self.system_daily_cost:.2f}"
            print(f"[COST] SYSTEM BUDGET EXCEEDED: {msg}")
            return False, msg

        return True, "OK"

    def record_cost(self, user_id: str, model: str, input_tokens: int, output_tokens: int) -> float:
        """Record cost for a request. Returns the cost."""
        cost = self.calculate_cost(model, input_tokens, output_tokens)

        self.user_daily_costs[user_id] = self.user_daily_costs.get(user_id, 0.0) + cost
        self.system_daily_cost += cost

        record = {
            "user_id": user_id,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
            "timestamp": time.time(),
        }
        self.request_costs.append(record)
        print(f"[COST] Request cost: ${cost:.6f} (model={model}, tokens={input_tokens}+{output_tokens})")
        return cost

    def get_user_report(self, user_id: str) -> dict:
        """Get cost report for a user."""
        user_requests = [r for r in self.request_costs if r["user_id"] == user_id]
        total = sum(r["cost"] for r in user_requests)
        return {
            "user_id": user_id,
            "total_cost": round(total, 6),
            "request_count": len(user_requests),
            "daily_budget_remaining": round(BUDGETS["per_user_daily"] - self.user_daily_costs.get(user_id, 0.0), 4),
        }

    def get_system_report(self) -> dict:
        """Get system-wide cost report."""
        return {
            "total_cost": round(self.system_daily_cost, 4),
            "total_requests": len(self.request_costs),
            "daily_budget_remaining": round(BUDGETS["system_daily"] - self.system_daily_cost, 2),
            "per_user": {uid: round(cost, 4) for uid, cost in self.user_daily_costs.items()},
        }


# Global instance
cost_tracker = CostTracker()
