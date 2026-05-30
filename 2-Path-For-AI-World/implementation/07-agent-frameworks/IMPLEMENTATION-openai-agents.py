"""
OpenAI Agents SDK Implementation
=================================

Demonstrates:
- Agent definition with instructions
- Function tool definitions
- Handoff between specialized agents
- Input/output guardrails
- Tracing integration
- Runner execution patterns
- Multi-agent orchestration
- Error handling
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from agents import (
    Agent,
    GuardrailFunctionOutput,
    InputGuardrail,
    OutputGuardrail,
    RunContextWrapper,
    Runner,
    Tool,
    function_tool,
    handoff,
    trace,
)
from agents.tracing import set_tracing_export_api_key
from pydantic import BaseModel, Field


# =============================================================================
# 1. TOOL DEFINITIONS
# =============================================================================

@function_tool
def search_knowledge_base(query: str) -> str:
    """Search the internal knowledge base for company information."""
    # Simulated - connect to your vector DB in production
    return f"Knowledge base results for '{query}': Company was founded in 2020, has 500 employees, revenue $50M ARR."


@function_tool
def get_customer_info(customer_id: str) -> str:
    """Look up customer information by their ID."""
    # Simulated
    customers = {
        "C001": {"name": "Acme Corp", "plan": "Enterprise", "mrr": 5000, "health": "good"},
        "C002": {"name": "StartupXYZ", "plan": "Pro", "mrr": 200, "health": "at_risk"},
    }
    customer = customers.get(customer_id)
    if customer:
        return json.dumps(customer)
    return f"Customer {customer_id} not found."


@function_tool
def create_support_ticket(
    customer_id: str, 
    subject: str, 
    priority: str, 
    description: str
) -> str:
    """Create a support ticket for the customer."""
    ticket_id = f"TKT-{hash(subject) % 10000:04d}"
    return f"Ticket {ticket_id} created for customer {customer_id}: {subject} (Priority: {priority})"


@function_tool
def escalate_to_human(reason: str, context: str) -> str:
    """Escalate the conversation to a human agent."""
    return f"Escalated to human agent. Reason: {reason}. A human will follow up shortly."


@function_tool
def check_order_status(order_id: str) -> str:
    """Check the status of a customer order."""
    orders = {
        "ORD-001": {"status": "shipped", "eta": "2024-03-15", "tracking": "1Z999AA10123456784"},
        "ORD-002": {"status": "processing", "eta": "2024-03-20", "tracking": None},
    }
    order = orders.get(order_id)
    if order:
        return json.dumps(order)
    return f"Order {order_id} not found."


@function_tool
def process_refund(order_id: str, amount: float, reason: str) -> str:
    """Process a refund for a customer order. Only for amounts under $500."""
    if amount > 500:
        return "ERROR: Refunds over $500 require manager approval. Please escalate."
    return f"Refund of ${amount:.2f} processed for order {order_id}. Reason: {reason}"


@function_tool  
def analyze_sentiment(text: str) -> str:
    """Analyze the sentiment of customer message."""
    # Simulated
    negative_words = {"angry", "frustrated", "terrible", "worst", "cancel", "hate"}
    words = set(text.lower().split())
    if words & negative_words:
        return json.dumps({"sentiment": "negative", "score": -0.8, "escalation_recommended": True})
    return json.dumps({"sentiment": "neutral", "score": 0.1, "escalation_recommended": False})


# =============================================================================
# 2. GUARDRAIL DEFINITIONS
# =============================================================================

class PIIDetectionResult(BaseModel):
    """Result of PII detection check."""
    contains_pii: bool
    pii_types: list[str] = Field(default_factory=list)
    sanitized_input: str


# Input guardrail: Block PII in user messages
async def pii_detection_guardrail(
    ctx: RunContextWrapper[Any], 
    agent: Agent, 
    input: str
) -> GuardrailFunctionOutput:
    """Detect and flag PII in user input."""
    # Simplified PII detection - use a proper NER model in production
    import re
    
    pii_patterns = {
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "credit_card": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
    }
    
    found_pii = []
    for pii_type, pattern in pii_patterns.items():
        if re.search(pattern, input):
            found_pii.append(pii_type)
    
    if "ssn" in found_pii or "credit_card" in found_pii:
        return GuardrailFunctionOutput(
            output_info=PIIDetectionResult(
                contains_pii=True,
                pii_types=found_pii,
                sanitized_input="[REDACTED - Contains sensitive PII]",
            ),
            tripwire_triggered=True,  # Block the request
        )
    
    return GuardrailFunctionOutput(
        output_info=PIIDetectionResult(
            contains_pii=bool(found_pii),
            pii_types=found_pii,
            sanitized_input=input,
        ),
        tripwire_triggered=False,
    )


# Output guardrail: Ensure no internal info leaks
async def no_internal_info_guardrail(
    ctx: RunContextWrapper[Any],
    agent: Agent,
    output: str,
) -> GuardrailFunctionOutput:
    """Ensure the agent doesn't leak internal system information."""
    blocked_patterns = [
        "internal api key",
        "database password",
        "admin credentials",
        "secret_",
        "sk-",  # API keys
    ]
    
    output_lower = output.lower()
    for pattern in blocked_patterns:
        if pattern in output_lower:
            return GuardrailFunctionOutput(
                output_info={"blocked": True, "reason": f"Contains blocked pattern: {pattern}"},
                tripwire_triggered=True,
            )
    
    return GuardrailFunctionOutput(
        output_info={"blocked": False},
        tripwire_triggered=False,
    )


# =============================================================================
# 3. AGENT DEFINITIONS
# =============================================================================

# Triage Agent - Routes to the right specialist
triage_agent = Agent(
    name="Triage Agent",
    instructions="""You are the first point of contact for customer support.
    
Your job is to:
1. Understand the customer's issue
2. Analyze sentiment to detect frustrated customers
3. Route to the appropriate specialist agent

Routing rules:
- Order/shipping questions → Order Specialist
- Billing/refund questions → Billing Specialist  
- Technical issues → Technical Support
- General questions → Answer directly using knowledge base
- Angry/frustrated customers → Escalate immediately

Always greet the customer warmly and acknowledge their issue before routing.""",
    tools=[search_knowledge_base, analyze_sentiment],
    input_guardrails=[
        InputGuardrail(guardrail_function=pii_detection_guardrail),
    ],
    output_guardrails=[
        OutputGuardrail(guardrail_function=no_internal_info_guardrail),
    ],
)

# Order Specialist Agent
order_specialist = Agent(
    name="Order Specialist",
    instructions="""You are an order and shipping specialist.

You can:
- Check order status and tracking information
- Explain shipping timelines
- Handle order-related issues

You CANNOT:
- Process refunds (hand off to Billing Specialist)
- Handle technical issues
- Make promises about delivery dates beyond what tracking shows

Always provide the tracking number when available.
If the customer is upset about shipping delays, empathize and offer to escalate.""",
    tools=[check_order_status, get_customer_info, escalate_to_human],
)

# Billing Specialist Agent
billing_specialist = Agent(
    name="Billing Specialist",
    instructions="""You are a billing and refund specialist.

You can:
- Process refunds under $500
- Explain billing charges
- Look up customer plan information

Rules:
- NEVER process refunds over $500 without escalating
- Always verify the customer ID before processing refunds
- Explain the refund timeline (5-7 business days)
- If a refund is denied by the system, explain why and offer alternatives""",
    tools=[process_refund, get_customer_info, create_support_ticket, escalate_to_human],
)

# Technical Support Agent
technical_specialist = Agent(
    name="Technical Support",
    instructions="""You are a technical support specialist.

You can:
- Troubleshoot common technical issues
- Search the knowledge base for solutions
- Create support tickets for complex issues
- Escalate to engineering if needed

Troubleshooting approach:
1. Ask clarifying questions about the issue
2. Search knowledge base for known solutions
3. Walk customer through steps
4. If unresolved, create a ticket and escalate""",
    tools=[search_knowledge_base, create_support_ticket, escalate_to_human],
)


# =============================================================================
# 4. HANDOFF CONFIGURATION
# =============================================================================

# Add handoffs to triage agent - this enables multi-agent routing
triage_agent = Agent(
    name="Triage Agent",
    instructions=triage_agent.instructions,
    tools=[search_knowledge_base, analyze_sentiment],
    handoffs=[
        handoff(order_specialist, description="Hand off to order specialist for shipping/order questions"),
        handoff(billing_specialist, description="Hand off to billing specialist for refund/payment questions"),
        handoff(technical_specialist, description="Hand off to technical support for product/technical issues"),
    ],
    input_guardrails=[
        InputGuardrail(guardrail_function=pii_detection_guardrail),
    ],
    output_guardrails=[
        OutputGuardrail(guardrail_function=no_internal_info_guardrail),
    ],
)

# Allow specialists to hand back to triage or escalate to each other
order_specialist = Agent(
    name="Order Specialist",
    instructions=order_specialist.instructions,
    tools=[check_order_status, get_customer_info, escalate_to_human],
    handoffs=[
        handoff(billing_specialist, description="Hand off to billing for refund requests"),
        handoff(triage_agent, description="Hand back to triage if issue is not order-related"),
    ],
)

billing_specialist = Agent(
    name="Billing Specialist", 
    instructions=billing_specialist.instructions,
    tools=[process_refund, get_customer_info, create_support_ticket, escalate_to_human],
    handoffs=[
        handoff(triage_agent, description="Hand back to triage if issue is not billing-related"),
    ],
)


# =============================================================================
# 5. RUNNER EXECUTION
# =============================================================================

async def handle_customer_query(user_message: str, session_id: str = "default"):
    """
    Handle a customer query through the multi-agent system.
    
    The Runner manages:
    - Agent execution loop
    - Tool calls
    - Handoffs between agents
    - Guardrail enforcement
    - Tracing
    """
    print(f"\n{'='*60}")
    print(f"Customer: {user_message}")
    print(f"{'='*60}")
    
    # Use trace context for observability
    with trace(
        workflow_name="customer_support",
        session_id=session_id,
        metadata={"channel": "chat", "priority": "normal"},
    ):
        try:
            result = await Runner.run(
                starting_agent=triage_agent,
                input=user_message,
                max_turns=15,  # Prevent infinite loops
            )
            
            print(f"\nAgent: {result.final_output}")
            print(f"Agent used: {result.last_agent.name}")
            print(f"Turns taken: {len(result.raw_responses)}")
            
            # Log handoff chain
            agents_involved = []
            for response in result.raw_responses:
                if hasattr(response, 'agent') and response.agent:
                    if not agents_involved or agents_involved[-1] != response.agent.name:
                        agents_involved.append(response.agent.name)
            
            if len(agents_involved) > 1:
                print(f"Handoff chain: {' → '.join(agents_involved)}")
            
            return result
            
        except Exception as e:
            print(f"\nError: {type(e).__name__}: {str(e)}")
            
            # Handle guardrail trips
            if "tripwire" in str(e).lower() or "guardrail" in str(e).lower():
                print("⚠️  Request blocked by guardrail. Please remove sensitive information.")
            
            raise


# =============================================================================
# 6. STREAMING EXECUTION
# =============================================================================

async def handle_customer_query_streaming(user_message: str):
    """Handle query with streaming output for real-time UI updates."""
    
    print(f"\nCustomer: {user_message}")
    print(f"Agent: ", end="", flush=True)
    
    async for event in Runner.run_streamed(
        starting_agent=triage_agent,
        input=user_message,
        max_turns=15,
    ):
        # Stream different event types
        if event.type == "raw_response_event":
            # Token-by-token streaming
            if hasattr(event.data, 'delta') and event.data.delta:
                print(event.data.delta, end="", flush=True)
        
        elif event.type == "agent_updated_stream_event":
            # Agent handoff occurred
            print(f"\n  [Handed off to: {event.new_agent.name}]")
            print(f"Agent: ", end="", flush=True)
        
        elif event.type == "tool_call_event":
            print(f"\n  [Calling: {event.tool_name}]", end="", flush=True)
        
        elif event.type == "run_item_stream_event":
            pass  # Handle other events as needed
    
    print()  # Final newline


# =============================================================================
# 7. CONTEXT / DEPENDENCY INJECTION
# =============================================================================

@dataclass
class CustomerContext:
    """Context passed to all agents during execution."""
    customer_id: str | None = None
    authenticated: bool = False
    language: str = "en"
    channel: str = "web"
    previous_tickets: list[str] = None
    
    def __post_init__(self):
        if self.previous_tickets is None:
            self.previous_tickets = []


# Agent with context-aware instructions
context_aware_agent = Agent(
    name="Context-Aware Support",
    instructions=lambda ctx: f"""You are a customer support agent.
    
Customer context:
- Customer ID: {ctx.context.customer_id or 'Unknown (not authenticated)'}
- Authenticated: {ctx.context.authenticated}
- Language: {ctx.context.language}
- Channel: {ctx.context.channel}
- Previous tickets: {len(ctx.context.previous_tickets)}

{'Greet them by name and reference their history.' if ctx.context.authenticated else 'Ask them to verify their identity first.'}
""",
    tools=[get_customer_info, search_knowledge_base, create_support_ticket],
)


async def handle_with_context(user_message: str, customer_ctx: CustomerContext):
    """Execute agent with customer context."""
    result = await Runner.run(
        starting_agent=context_aware_agent,
        input=user_message,
        context=customer_ctx,
    )
    return result


# =============================================================================
# 8. ERROR HANDLING PATTERNS
# =============================================================================

async def robust_agent_execution(user_message: str, max_retries: int = 3):
    """Production-grade execution with error handling."""
    
    for attempt in range(max_retries):
        try:
            result = await Runner.run(
                starting_agent=triage_agent,
                input=user_message,
                max_turns=15,
            )
            return result
            
        except Exception as e:
            error_type = type(e).__name__
            
            # Guardrail violations - don't retry
            if "guardrail" in str(e).lower():
                return {
                    "error": "Request blocked by safety guardrail",
                    "type": "guardrail_violation",
                    "retry": False,
                }
            
            # Rate limits - retry with backoff
            if "rate_limit" in str(e).lower() or "429" in str(e):
                wait_time = 2 ** attempt
                print(f"Rate limited. Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
                continue
            
            # Max turns exceeded - agent might be in a loop
            if "max_turns" in str(e).lower():
                return {
                    "error": "Agent exceeded maximum turns. Escalating to human.",
                    "type": "max_turns_exceeded",
                    "retry": False,
                }
            
            # Unknown error on last attempt
            if attempt == max_retries - 1:
                return {
                    "error": f"Failed after {max_retries} attempts: {error_type}: {str(e)}",
                    "type": "unknown_error",
                    "retry": False,
                }
            
            await asyncio.sleep(1)
    
    return {"error": "Exhausted retries", "type": "retry_exhausted", "retry": False}


# =============================================================================
# 9. MAIN EXECUTION
# =============================================================================

async def main():
    """Run example customer support scenarios."""
    
    # Scenario 1: Order tracking
    await handle_customer_query(
        "Hi, I ordered something last week (order ORD-001) and want to know where it is.",
        session_id="session-001",
    )
    
    # Scenario 2: Refund request (routes to billing)
    await handle_customer_query(
        "I need a refund for order ORD-002. The item arrived damaged. It was $150.",
        session_id="session-002",
    )
    
    # Scenario 3: PII detection (guardrail blocks)
    try:
        await handle_customer_query(
            "My credit card is 4111-1111-1111-1111 and I need help with billing.",
            session_id="session-003",
        )
    except Exception as e:
        print(f"Blocked as expected: {e}")
    
    # Scenario 4: Frustrated customer (escalation)
    await handle_customer_query(
        "This is terrible! I've been waiting 3 weeks and nobody has helped me. I want to cancel everything!",
        session_id="session-004",
    )
    
    # Scenario 5: With customer context
    ctx = CustomerContext(
        customer_id="C001",
        authenticated=True,
        language="en",
        channel="web",
        previous_tickets=["TKT-0001", "TKT-0042"],
    )
    await handle_with_context(
        "What's my current plan and how much am I paying?",
        customer_ctx=ctx,
    )


if __name__ == "__main__":
    asyncio.run(main())
