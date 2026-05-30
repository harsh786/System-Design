"""
Multi-Agent Systems: Router-Specialist Pattern
===============================================

Production implementation of the router-specialist pattern where a lightweight
router classifies incoming queries and routes them to domain-specific specialist
agents, with health checking, fallback routing, and conversation handoff.
"""

import asyncio
import uuid
import time
import re
from enum import Enum
from typing import Any, Optional
from dataclasses import dataclass, field
from abc import ABC, abstractmethod


# =============================================================================
# Core Types
# =============================================================================

class RoutingDecision(Enum):
    CONFIDENT = "confident"       # High confidence, route directly
    UNCERTAIN = "uncertain"       # Low confidence, ask clarifying question
    FALLBACK = "fallback"         # No specialist matches, use generalist
    ESCALATE = "escalate"         # Needs human


@dataclass
class RoutingResult:
    specialist_id: str
    confidence: float
    decision: RoutingDecision
    reasoning: str
    metadata: dict = field(default_factory=dict)


@dataclass
class ConversationContext:
    conversation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    messages: list[dict] = field(default_factory=list)
    current_specialist: Optional[str] = None
    handoff_count: int = 0
    total_cost: float = 0.0
    routing_history: list[dict] = field(default_factory=list)


@dataclass
class SpecialistHealth:
    is_healthy: bool = True
    last_check: float = field(default_factory=time.time)
    consecutive_failures: int = 0
    avg_latency: float = 0.0
    success_rate: float = 1.0
    total_requests: int = 0


@dataclass
class RoutingMetrics:
    total_routed: int = 0
    routes_per_specialist: dict = field(default_factory=dict)
    avg_confidence: float = 0.0
    fallback_count: int = 0
    handoff_count: int = 0
    misroute_count: int = 0  # Detected via user correction


# =============================================================================
# Specialist Base Class
# =============================================================================

class Specialist(ABC):
    """Base class for domain-specific specialist agents."""

    def __init__(self, specialist_id: str, domain: str, 
                 description: str, keywords: list[str]):
        self.specialist_id = specialist_id
        self.domain = domain
        self.description = description
        self.keywords = keywords  # For rule-based routing
        self.health = SpecialistHealth()
        self.system_prompt = self._build_system_prompt()

    @abstractmethod
    def _build_system_prompt(self) -> str:
        pass

    @abstractmethod
    async def handle(self, query: str, context: ConversationContext) -> dict:
        pass

    def matches_keywords(self, query: str) -> float:
        """Rule-based matching score (0-1)."""
        query_lower = query.lower()
        matches = sum(1 for kw in self.keywords if kw.lower() in query_lower)
        return min(1.0, matches / max(1, len(self.keywords) * 0.3))

    def update_health(self, success: bool, latency: float):
        self.health.total_requests += 1
        if success:
            self.health.consecutive_failures = 0
        else:
            self.health.consecutive_failures += 1
            if self.health.consecutive_failures >= 3:
                self.health.is_healthy = False
        
        # Running average
        n = self.health.total_requests
        self.health.avg_latency = (self.health.avg_latency * (n-1) + latency) / n
        self.health.success_rate = (
            (self.health.success_rate * (n-1) + (1.0 if success else 0.0)) / n
        )
        self.health.last_check = time.time()


# =============================================================================
# Concrete Specialists
# =============================================================================

class BillingSpecialist(Specialist):
    """Handles billing, payments, invoices, and subscription queries."""

    def __init__(self):
        super().__init__(
            specialist_id="billing",
            domain="billing_and_payments",
            description="Handles billing, payments, invoices, subscriptions, refunds, pricing",
            keywords=["bill", "invoice", "payment", "charge", "refund", "subscription",
                     "pricing", "plan", "upgrade", "downgrade", "cancel", "cost", "fee"]
        )

    def _build_system_prompt(self) -> str:
        return """You are a billing specialist agent. You help customers with:
- Understanding their invoices and charges
- Processing refunds and credits
- Managing subscriptions (upgrade, downgrade, cancel)
- Explaining pricing plans
- Resolving payment failures

Always be precise with amounts. Never promise refunds without checking eligibility.
If a request requires account changes, confirm with the customer before proceeding."""

    async def handle(self, query: str, context: ConversationContext) -> dict:
        await asyncio.sleep(0.3)  # Simulate LLM call
        return {
            "response": f"[Billing Specialist] I can help with your billing question: '{query[:50]}...'. "
                       f"Let me look into your account details.",
            "actions_taken": ["looked_up_account"],
            "needs_followup": False,
            "confidence": 0.9,
            "cost": 0.002,
        }


class TechnicalSpecialist(Specialist):
    """Handles technical support, API issues, debugging."""

    def __init__(self):
        super().__init__(
            specialist_id="technical",
            domain="technical_support",
            description="Handles API issues, bugs, integration problems, technical debugging",
            keywords=["error", "bug", "api", "endpoint", "timeout", "crash", "code",
                     "integration", "sdk", "debug", "log", "500", "404", "authentication",
                     "token", "webhook", "rate limit"]
        )

    def _build_system_prompt(self) -> str:
        return """You are a technical support specialist. You help with:
- API errors and debugging
- Integration issues
- SDK and library problems
- Authentication and authorization
- Rate limiting and performance

Always ask for error messages and status codes. Guide users through debugging steps.
If the issue requires engineering escalation, collect all relevant details first."""

    async def handle(self, query: str, context: ConversationContext) -> dict:
        await asyncio.sleep(0.4)  # Simulate LLM call
        return {
            "response": f"[Technical Specialist] I'll help debug this issue. "
                       f"Can you share the error message and status code you're seeing?",
            "actions_taken": ["checked_system_status"],
            "needs_followup": True,
            "confidence": 0.85,
            "cost": 0.003,
        }


class OnboardingSpecialist(Specialist):
    """Handles new user setup, getting started, feature discovery."""

    def __init__(self):
        super().__init__(
            specialist_id="onboarding",
            domain="onboarding_and_setup",
            description="Handles setup, getting started, feature discovery, tutorials",
            keywords=["start", "setup", "begin", "new", "how to", "tutorial",
                     "getting started", "first", "learn", "guide", "feature", "what can"]
        )

    def _build_system_prompt(self) -> str:
        return """You are an onboarding specialist. You help new users:
- Set up their account and workspace
- Discover relevant features
- Follow getting-started guides
- Understand core concepts

Be welcoming and encouraging. Use step-by-step instructions.
Proactively suggest next steps after each completed action."""

    async def handle(self, query: str, context: ConversationContext) -> dict:
        await asyncio.sleep(0.3)
        return {
            "response": f"[Onboarding Specialist] Welcome! I'll help you get started. "
                       f"Let me walk you through the setup process step by step.",
            "actions_taken": ["identified_user_stage"],
            "needs_followup": True,
            "confidence": 0.92,
            "cost": 0.002,
        }


class GeneralistSpecialist(Specialist):
    """Fallback generalist that handles anything not matching a specialist."""

    def __init__(self):
        super().__init__(
            specialist_id="generalist",
            domain="general",
            description="Handles general queries that don't fit specific domains",
            keywords=[]
        )

    def _build_system_prompt(self) -> str:
        return """You are a helpful general assistant. Handle queries that don't fit 
specific specialist domains. If you detect the query actually belongs to a specialist 
domain, indicate that in your response metadata."""

    async def handle(self, query: str, context: ConversationContext) -> dict:
        await asyncio.sleep(0.3)
        return {
            "response": f"[Generalist] I'll do my best to help with: '{query[:50]}...'",
            "actions_taken": [],
            "needs_followup": False,
            "confidence": 0.6,
            "cost": 0.002,
            "suggested_specialist": None,  # Could suggest rerouting
        }


# =============================================================================
# Router Agent
# =============================================================================

class RouterAgent:
    """
    Lightweight router that classifies queries and routes to specialists.
    Uses hybrid approach: rule-based first, LLM-based for ambiguous cases.
    """

    def __init__(self, specialists: list[Specialist],
                 confidence_threshold: float = 0.6,
                 max_handoffs_per_conversation: int = 3):
        self.specialists = {s.specialist_id: s for s in specialists}
        self.confidence_threshold = confidence_threshold
        self.max_handoffs = max_handoffs_per_conversation
        self.metrics = RoutingMetrics()
        
        # Ensure generalist exists as fallback
        if "generalist" not in self.specialists:
            self.specialists["generalist"] = GeneralistSpecialist()

    async def route(self, query: str, context: ConversationContext) -> RoutingResult:
        """
        Route a query to the best specialist.
        Strategy: rules first → LLM for ambiguous → fallback.
        """
        # Step 1: Rule-based classification (fast, cheap)
        rule_scores = {}
        for sid, specialist in self.specialists.items():
            if sid == "generalist":
                continue
            score = specialist.matches_keywords(query)
            if score > 0:
                rule_scores[sid] = score
        
        # If clear winner from rules, route directly
        if rule_scores:
            best_rule = max(rule_scores, key=rule_scores.get)
            if rule_scores[best_rule] >= 0.7:
                return RoutingResult(
                    specialist_id=best_rule,
                    confidence=rule_scores[best_rule],
                    decision=RoutingDecision.CONFIDENT,
                    reasoning=f"Rule-based match (score: {rule_scores[best_rule]:.2f})"
                )
        
        # Step 2: LLM-based classification (for ambiguous cases)
        llm_result = await self._llm_classify(query, context)
        
        # Step 3: Combine scores
        final_scores = {}
        for sid in self.specialists:
            if sid == "generalist":
                continue
            rule_score = rule_scores.get(sid, 0.0)
            llm_score = llm_result.get(sid, 0.0)
            # Weighted combination
            final_scores[sid] = rule_score * 0.3 + llm_score * 0.7
        
        if not final_scores or max(final_scores.values()) < self.confidence_threshold:
            # Check if we should ask clarifying question or use fallback
            if max(final_scores.values(), default=0) > 0.3:
                return RoutingResult(
                    specialist_id="generalist",
                    confidence=max(final_scores.values(), default=0),
                    decision=RoutingDecision.UNCERTAIN,
                    reasoning="Low confidence, asking for clarification"
                )
            return RoutingResult(
                specialist_id="generalist",
                confidence=0.5,
                decision=RoutingDecision.FALLBACK,
                reasoning="No specialist matched with sufficient confidence"
            )
        
        best_specialist = max(final_scores, key=final_scores.get)
        confidence = final_scores[best_specialist]
        
        # Health check
        if not self.specialists[best_specialist].health.is_healthy:
            # Route to next best or fallback
            sorted_specialists = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
            for sid, score in sorted_specialists[1:]:
                if self.specialists[sid].health.is_healthy and score > self.confidence_threshold:
                    return RoutingResult(
                        specialist_id=sid,
                        confidence=score,
                        decision=RoutingDecision.CONFIDENT,
                        reasoning=f"Primary ({best_specialist}) unhealthy, routing to backup"
                    )
            return RoutingResult(
                specialist_id="generalist",
                confidence=0.5,
                decision=RoutingDecision.FALLBACK,
                reasoning=f"Primary specialist {best_specialist} unhealthy, using generalist"
            )
        
        return RoutingResult(
            specialist_id=best_specialist,
            confidence=confidence,
            decision=RoutingDecision.CONFIDENT,
            reasoning=f"Best match (score: {confidence:.2f})"
        )

    async def _llm_classify(self, query: str, context: ConversationContext) -> dict[str, float]:
        """
        Use LLM to classify query intent.
        In production: actual LLM call with structured output.
        """
        # Simulated LLM classification
        await asyncio.sleep(0.1)
        
        scores = {}
        query_lower = query.lower()
        
        # Simulated intent detection
        if any(w in query_lower for w in ["pay", "bill", "charge", "refund", "price"]):
            scores["billing"] = 0.9
        if any(w in query_lower for w in ["error", "bug", "api", "crash", "debug"]):
            scores["technical"] = 0.9
        if any(w in query_lower for w in ["start", "setup", "new", "how to", "begin"]):
            scores["onboarding"] = 0.85
        
        # Add some noise for realism
        for sid in self.specialists:
            if sid not in scores and sid != "generalist":
                scores[sid] = 0.1
        
        return scores

    def _update_metrics(self, result: RoutingResult):
        self.metrics.total_routed += 1
        sid = result.specialist_id
        self.metrics.routes_per_specialist[sid] = \
            self.metrics.routes_per_specialist.get(sid, 0) + 1
        
        # Running average confidence
        n = self.metrics.total_routed
        self.metrics.avg_confidence = (
            (self.metrics.avg_confidence * (n-1) + result.confidence) / n
        )
        
        if result.decision == RoutingDecision.FALLBACK:
            self.metrics.fallback_count += 1


# =============================================================================
# Conversation Orchestrator
# =============================================================================

class ConversationOrchestrator:
    """
    Manages multi-turn conversations with routing between specialists,
    handling handoffs, context passing, and conversation state.
    """

    def __init__(self, router: RouterAgent):
        self.router = router
        self.active_conversations: dict[str, ConversationContext] = {}

    async def handle_message(self, conversation_id: str, user_message: str) -> dict:
        """Process a user message within a conversation."""
        # Get or create conversation context
        if conversation_id not in self.active_conversations:
            self.active_conversations[conversation_id] = ConversationContext(
                conversation_id=conversation_id
            )
        
        context = self.active_conversations[conversation_id]
        context.messages.append({"role": "user", "content": user_message})
        
        # Route the message
        routing_result = await self.router.route(user_message, context)
        self.router._update_metrics(routing_result)
        
        # Handle handoff if specialist changed
        if (context.current_specialist and 
            routing_result.specialist_id != context.current_specialist):
            context.handoff_count += 1
            self.router.metrics.handoff_count += 1
            print(f"  [Handoff] {context.current_specialist} → {routing_result.specialist_id}")
        
        context.current_specialist = routing_result.specialist_id
        context.routing_history.append({
            "message": user_message[:50],
            "routed_to": routing_result.specialist_id,
            "confidence": routing_result.confidence,
            "decision": routing_result.decision.value,
        })
        
        # Handle uncertain routing
        if routing_result.decision == RoutingDecision.UNCERTAIN:
            return {
                "response": "I want to make sure I route you to the right specialist. "
                           "Could you tell me more about what you need help with?",
                "specialist": None,
                "confidence": routing_result.confidence,
                "needs_clarification": True,
            }
        
        # Execute with specialist
        specialist = self.router.specialists[routing_result.specialist_id]
        start_time = time.time()
        
        try:
            result = await specialist.handle(user_message, context)
            latency = time.time() - start_time
            specialist.update_health(True, latency)
            
            # Update context
            context.messages.append({
                "role": "assistant",
                "content": result["response"],
                "specialist": routing_result.specialist_id,
            })
            context.total_cost += result.get("cost", 0)
            
            return {
                "response": result["response"],
                "specialist": routing_result.specialist_id,
                "confidence": routing_result.confidence,
                "routing_reasoning": routing_result.reasoning,
                "cost": result.get("cost", 0),
                "needs_followup": result.get("needs_followup", False),
            }
            
        except Exception as e:
            latency = time.time() - start_time
            specialist.update_health(False, latency)
            
            # Fallback to generalist
            generalist = self.router.specialists["generalist"]
            result = await generalist.handle(user_message, context)
            
            return {
                "response": result["response"],
                "specialist": "generalist",
                "confidence": 0.5,
                "routing_reasoning": f"Fallback after {specialist.specialist_id} failed: {e}",
                "cost": result.get("cost", 0),
                "error": str(e),
            }

    def get_conversation_summary(self, conversation_id: str) -> dict:
        """Get summary of a conversation for debugging/monitoring."""
        context = self.active_conversations.get(conversation_id)
        if not context:
            return {"error": "Conversation not found"}
        
        return {
            "conversation_id": conversation_id,
            "message_count": len(context.messages),
            "current_specialist": context.current_specialist,
            "handoff_count": context.handoff_count,
            "total_cost": context.total_cost,
            "routing_history": context.routing_history,
        }


# =============================================================================
# Demo
# =============================================================================

async def main():
    print("=" * 70)
    print("ROUTER-SPECIALIST PATTERN DEMO")
    print("=" * 70)
    
    # Create specialists
    specialists = [
        BillingSpecialist(),
        TechnicalSpecialist(),
        OnboardingSpecialist(),
        GeneralistSpecialist(),
    ]
    
    # Create router
    router = RouterAgent(
        specialists=specialists,
        confidence_threshold=0.5,
    )
    
    # Create orchestrator
    orchestrator = ConversationOrchestrator(router)
    
    # Simulate a multi-turn conversation with domain switches
    conversation_id = "conv-001"
    
    messages = [
        "Hi, I'm getting a 500 error when calling the /users endpoint",
        "Actually, I also noticed I was charged twice this month",
        "Can you help me set up webhooks? I'm new to the platform",
    ]
    
    for msg in messages:
        print(f"\n{'─' * 50}")
        print(f"  User: {msg}")
        print(f"{'─' * 50}")
        
        result = await orchestrator.handle_message(conversation_id, msg)
        
        print(f"  Routed to: {result['specialist']} (confidence: {result['confidence']:.2f})")
        print(f"  Reasoning: {result.get('routing_reasoning', 'N/A')}")
        print(f"  Response: {result['response'][:100]}...")
        print(f"  Cost: ${result.get('cost', 0):.4f}")
    
    # Print conversation summary
    print(f"\n{'=' * 70}")
    print("CONVERSATION SUMMARY")
    print(f"{'=' * 70}")
    summary = orchestrator.get_conversation_summary(conversation_id)
    print(f"  Messages: {summary['message_count']}")
    print(f"  Handoffs: {summary['handoff_count']}")
    print(f"  Total cost: ${summary['total_cost']:.4f}")
    print(f"  Routing history:")
    for entry in summary['routing_history']:
        print(f"    → {entry['routed_to']} ({entry['confidence']:.2f}) [{entry['decision']}]")
    
    # Print routing metrics
    print(f"\n{'=' * 70}")
    print("ROUTING METRICS")
    print(f"{'=' * 70}")
    metrics = router.metrics
    print(f"  Total routed: {metrics.total_routed}")
    print(f"  Avg confidence: {metrics.avg_confidence:.2f}")
    print(f"  Fallbacks: {metrics.fallback_count}")
    print(f"  Handoffs: {metrics.handoff_count}")
    print(f"  Per specialist: {metrics.routes_per_specialist}")


if __name__ == "__main__":
    asyncio.run(main())
