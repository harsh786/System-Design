# Agent Frameworks: Real-World Examples

## Case Study 1: Series B Startup Chooses LangGraph for Customer Support Platform

### Context

**Company:** HelioSupport (Series B, $28M raised, 45 engineers)
**Problem:** Building an AI customer support platform handling 50K tickets/day across email, chat, and phone transcripts.
**Timeline:** 8 weeks to MVP, 16 weeks to production.

### Evaluation Criteria

The team evaluated LangGraph, CrewAI, and AutoGen across these dimensions:

| Criterion | Weight | LangGraph | CrewAI | AutoGen |
|-----------|--------|-----------|--------|---------|
| State management | 25% | 9/10 | 5/10 | 6/10 |
| Human-in-the-loop | 20% | 9/10 | 4/10 | 7/10 |
| Production observability | 15% | 8/10 | 4/10 | 5/10 |
| Deterministic workflows | 15% | 9/10 | 3/10 | 4/10 |
| Learning curve | 10% | 5/10 | 8/10 | 6/10 |
| Community/ecosystem | 10% | 8/10 | 6/10 | 7/10 |
| Scalability evidence | 5% | 8/10 | 4/10 | 5/10 |

### Why CrewAI Was Eliminated (Week 2)

```python
# CrewAI prototype - worked for demo, failed for production
from crewai import Agent, Task, Crew

# Problem 1: No native state persistence between turns
# Customer says "I already told the previous agent my order number"
# CrewAI has no built-in mechanism to carry conversational state

support_agent = Agent(
    role="Customer Support Specialist",
    goal="Resolve customer issues efficiently",
    backstory="You are a senior support agent...",
    tools=[lookup_order, check_inventory, process_refund]
)

# Problem 2: Non-deterministic task routing
# For compliance, they needed GUARANTEED routing:
# - Refund > $500 → always escalate to human
# - Legal language detected → always route to legal team
# CrewAI's role-based delegation couldn't enforce this

# Problem 3: No checkpointing
# If the process crashed mid-refund, there was no way to resume
# without re-running the entire conversation from scratch
```

**Specific failure:** During load testing, CrewAI's agent delegation caused a feedback loop where the "router agent" and "specialist agent" kept delegating back to each other. This consumed 47 LLM calls for a single ticket before timing out. No built-in cycle detection existed.

### Why AutoGen Was a Close Second

```python
# AutoGen prototype - good multi-agent patterns, weak on persistence
import autogen

# AutoGen's GroupChat worked well for multi-agent collaboration
config_list = [{"model": "gpt-4", "api_key": os.environ["OPENAI_API_KEY"]}]

# What worked: clear agent boundaries
triage_agent = autogen.AssistantAgent(
    name="TriageAgent",
    system_message="Classify tickets into: billing, technical, account, escalation"
)

billing_agent = autogen.AssistantAgent(
    name="BillingAgent", 
    system_message="Handle billing inquiries. You can issue refunds up to $100."
)

# What failed: state management at scale
# AutoGen stores conversation as a flat list of messages
# At 50K tickets/day, they needed:
# 1. Per-ticket isolated state
# 2. Cross-ticket customer context (previous interactions)
# 3. Durable checkpoints for crash recovery
# 4. Branching (try refund → if rejected → try credit → if rejected → escalate)

# AutoGen's GroupChat doesn't natively support:
# - Persistent state across process restarts
# - Conditional branching based on tool outputs
# - Human-in-the-loop with async approval workflows
```

**Deciding factor:** AutoGen required wrapping every state mutation in custom Redis persistence code. The team estimated 3 extra weeks of infrastructure work that LangGraph provided out-of-the-box.

### The Winning LangGraph Architecture

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from typing import TypedDict, Literal, Annotated
import operator

class TicketState(TypedDict):
    ticket_id: str
    customer_id: str
    messages: Annotated[list, operator.add]
    classification: str
    sentiment_score: float
    refund_amount: float
    escalation_reason: str
    resolution_status: str
    human_approval_needed: bool
    tools_called: list[str]
    retry_count: int

def classify_ticket(state: TicketState) -> TicketState:
    """Deterministic classification with fallback."""
    response = llm.invoke(
        f"Classify this ticket: {state['messages'][-1]}\n"
        f"Categories: billing, technical, account, legal, escalation"
    )
    return {"classification": response.content, "sentiment_score": analyze_sentiment(state)}

def route_after_classification(state: TicketState) -> Literal["billing", "technical", "escalation", "human"]:
    """Hard-coded routing rules that CANNOT be overridden by LLM."""
    if "legal" in state["classification"].lower():
        return "human"  # Always escalate legal
    if state["sentiment_score"] < 0.2:
        return "human"  # Very angry customer → human
    if state["refund_amount"] > 500:
        return "human"  # High-value refund → human approval
    return state["classification"]

# Build the graph
workflow = StateGraph(TicketState)
workflow.add_node("classify", classify_ticket)
workflow.add_node("billing", handle_billing)
workflow.add_node("technical", handle_technical)
workflow.add_node("escalation", handle_escalation)
workflow.add_node("human_review", await_human_review)
workflow.add_node("resolve", resolve_ticket)

workflow.set_entry_point("classify")
workflow.add_conditional_edges("classify", route_after_classification)
workflow.add_edge("billing", "resolve")
workflow.add_edge("technical", "resolve")
workflow.add_edge("human_review", "resolve")

# PostgreSQL checkpointing — survives process crashes
checkpointer = PostgresSaver.from_conn_string(DATABASE_URL)
app = workflow.compile(checkpointer=checkpointer)
```

### Production Results (After 16 Weeks)

- **Ticket resolution rate:** 73% fully automated (up from 12% with rules-based system)
- **Average resolution time:** 2.3 minutes (down from 4.2 hours with human agents)
- **Crash recovery:** 100% of in-flight tickets resumed correctly after deploys
- **Human escalation accuracy:** 94% (only 6% of escalations were unnecessary)
- **Cost:** $0.12 per ticket (LLM costs) vs $4.50 per ticket (human agent)

---

## Case Study 2: OpenAI Agents SDK — Multi-Step Research Assistant

### Architecture Overview

**Use case:** Investment research assistant that analyzes companies by pulling data from multiple sources, synthesizing findings, and producing a structured report.

```python
from agents import Agent, Runner, function_tool, handoff, GuardrailFunctionOutput
from agents.tracing import trace
import asyncio

# Tool definitions with strict typing
@function_tool
def search_sec_filings(ticker: str, filing_type: str = "10-K", years: int = 3) -> str:
    """Search SEC EDGAR for company filings."""
    filings = sec_client.get_filings(ticker, filing_type, years)
    return json.dumps([{
        "date": f.date, 
        "revenue": f.financials.revenue,
        "net_income": f.financials.net_income,
        "key_risks": f.risk_factors[:5]
    } for f in filings])

@function_tool
def analyze_competitors(ticker: str) -> str:
    """Identify and analyze top 5 competitors."""
    competitors = market_data.get_competitors(ticker)
    return json.dumps([{
        "name": c.name,
        "market_cap": c.market_cap,
        "growth_rate": c.revenue_growth,
        "moat": c.competitive_advantage
    } for c in competitors[:5]])

@function_tool
def get_analyst_consensus(ticker: str) -> str:
    """Get Wall Street analyst ratings and price targets."""
    consensus = analyst_api.get_consensus(ticker)
    return json.dumps({
        "buy": consensus.buy_count,
        "hold": consensus.hold_count,
        "sell": consensus.sell_count,
        "avg_price_target": consensus.avg_target,
        "upside_pct": consensus.upside_percentage
    })

@function_tool
def search_news(query: str, days: int = 30) -> str:
    """Search recent news articles."""
    articles = news_api.search(query, days=days)
    return json.dumps([{"title": a.title, "summary": a.summary, "date": a.date} for a in articles[:10]])

# Specialist agents
financial_analyst = Agent(
    name="FinancialAnalyst",
    instructions="""You are a senior financial analyst. Analyze company financials 
    from SEC filings. Focus on: revenue trends, margin expansion/compression, 
    cash flow quality, and debt levels. Always cite specific numbers.""",
    tools=[search_sec_filings, get_analyst_consensus],
    model="gpt-4o"
)

competitive_analyst = Agent(
    name="CompetitiveAnalyst", 
    instructions="""You are a competitive intelligence specialist. Analyze market 
    positioning, competitive moats, and threats. Use Porter's Five Forces framework.""",
    tools=[analyze_competitors, search_news],
    model="gpt-4o"
)

# Orchestrator agent with handoffs
research_director = Agent(
    name="ResearchDirector",
    instructions="""You are a research director coordinating an investment analysis.
    
    Workflow:
    1. First, delegate financial analysis to FinancialAnalyst
    2. Then, delegate competitive analysis to CompetitiveAnalyst  
    3. Synthesize both analyses into a final investment thesis
    4. Provide a clear BUY/HOLD/SELL recommendation with conviction level
    
    Always ensure both analyses complete before synthesizing.""",
    handoffs=[
        handoff(financial_analyst, tool_name="delegate_to_financial_analyst",
                tool_description="Delegate financial analysis tasks"),
        handoff(competitive_analyst, tool_name="delegate_to_competitive_analyst",
                tool_description="Delegate competitive intelligence tasks"),
    ],
    model="gpt-4o"
)

# Guardrail: Prevent hallucinated financial data
@guardrail
def verify_no_hallucinated_numbers(output: str) -> GuardrailFunctionOutput:
    """Ensure all financial figures are sourced from tools, not fabricated."""
    # Check that any dollar amount or percentage in output 
    # was present in a tool response
    numbers = extract_numbers(output)
    tool_numbers = extract_numbers_from_tool_responses()
    unsourced = [n for n in numbers if n not in tool_numbers]
    if unsourced:
        return GuardrailFunctionOutput(
            tripwire=True,
            output_info=f"Unsourced numbers detected: {unsourced}"
        )
    return GuardrailFunctionOutput(tripwire=False)

# Execution with tracing
async def run_research(ticker: str):
    with trace(f"research-{ticker}"):
        result = await Runner.run(
            research_director,
            input=f"Produce a comprehensive investment analysis for {ticker}. "
                  f"Include financial health, competitive position, and final recommendation.",
            max_turns=15
        )
        return result.final_output
```

### Key Architectural Decisions

1. **Handoffs over multi-agent chat:** OpenAI Agents SDK uses explicit handoffs rather than free-form agent conversation. This prevents the "chatty agents" problem where agents waste tokens coordinating.

2. **Guardrails as first-class citizens:** The SDK allows input/output guardrails that can halt execution. Critical for financial applications where hallucinated numbers could cause real harm.

3. **Tracing built-in:** Every agent turn, tool call, and handoff is automatically traced. No additional observability infrastructure needed for debugging.

---

## Case Study 3: LangGraph at Fortune 500 — Production Patterns

### Company Context

**Company:** Global insurance company (Fortune 200, $80B AUM)
**System:** Claims processing automation handling 200K claims/month
**Team:** 12 ML engineers, 4 platform engineers

### State Management Pattern: Hierarchical State

```python
from langgraph.graph import StateGraph
from typing import TypedDict, Optional
from datetime import datetime

class ClaimState(TypedDict):
    # Immutable context
    claim_id: str
    policy_number: str
    claimant_name: str
    incident_date: datetime
    
    # Mutable processing state  
    documents_extracted: list[dict]
    fraud_score: float
    damage_assessment: dict
    coverage_verification: dict
    
    # Workflow control
    current_step: str
    requires_human_review: bool
    human_reviewer_id: Optional[str]
    human_decision: Optional[str]
    
    # Audit trail (append-only)
    audit_log: list[dict]
    
    # Error handling
    error_count: int
    last_error: Optional[str]
    retry_eligible: bool

class DocumentExtractionSubstate(TypedDict):
    """Substate for document extraction node — isolates complexity."""
    raw_documents: list[bytes]
    extracted_fields: dict
    confidence_scores: dict
    extraction_model_version: str
    
def extract_documents(state: ClaimState) -> ClaimState:
    """Extract information from uploaded claim documents."""
    docs = document_store.get_documents(state["claim_id"])
    
    extracted = []
    for doc in docs:
        result = extraction_model.extract(doc)
        extracted.append({
            "doc_type": result.document_type,
            "fields": result.fields,
            "confidence": result.confidence,
            "model_version": "v3.2.1"
        })
    
    # Append to audit log (never overwrite)
    audit_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "step": "document_extraction",
        "documents_processed": len(docs),
        "avg_confidence": sum(e["confidence"] for e in extracted) / len(extracted)
    }
    
    return {
        "documents_extracted": extracted,
        "audit_log": [audit_entry],
        "current_step": "fraud_check"
    }
```

### Checkpointing Strategy

```python
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.base import CheckpointMetadata

# Production checkpointing with metadata for debugging
checkpointer = PostgresSaver.from_conn_string(
    "postgresql://claims_user:***@claims-db.internal:5432/langgraph_checkpoints"
)

# Custom checkpoint metadata for compliance
class ComplianceCheckpointer(PostgresSaver):
    def put(self, config, checkpoint, metadata):
        # Add compliance metadata
        enhanced_metadata = {
            **metadata,
            "compliance_timestamp": datetime.utcnow().isoformat(),
            "data_classification": "PII-SENSITIVE",
            "retention_policy": "7_YEARS",
            "encryption_key_id": get_current_key_id()
        }
        super().put(config, checkpoint, enhanced_metadata)

# Checkpoint pruning (required for 200K claims/month)
# Each claim generates ~15 checkpoints × 200K = 3M checkpoints/month
async def prune_old_checkpoints():
    """Run nightly: remove intermediate checkpoints for resolved claims."""
    resolved_claims = await db.fetch(
        "SELECT claim_id FROM claims WHERE status = 'resolved' AND resolved_at < NOW() - INTERVAL '30 days'"
    )
    for claim in resolved_claims:
        # Keep only first and last checkpoint (for audit)
        checkpoints = await checkpointer.list({"configurable": {"thread_id": claim.claim_id}})
        if len(checkpoints) > 2:
            for cp in checkpoints[1:-1]:
                await checkpointer.delete(cp.checkpoint_id)
```

### Human-in-the-Loop Implementation

```python
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

def should_escalate(state: ClaimState) -> str:
    """Deterministic escalation rules (not LLM-decided)."""
    if state["fraud_score"] > 0.7:
        return "human_review"
    if state["damage_assessment"].get("total_amount", 0) > 50000:
        return "human_review"
    if state["coverage_verification"].get("disputed", False):
        return "human_review"
    return "auto_approve"

def human_review_node(state: ClaimState) -> ClaimState:
    """This node BLOCKS until human provides input.
    
    In production, this works via:
    1. Graph execution pauses (checkpoint saved)
    2. Notification sent to reviewer via Slack/email
    3. Reviewer opens internal UI, sees claim context
    4. Reviewer submits decision via API
    5. API call resumes graph with human_decision populated
    """
    # This is where LangGraph's interrupt() mechanism shines
    # The graph literally stops here and resumes when called with updated state
    return {
        "requires_human_review": True,
        "current_step": "awaiting_human",
        "audit_log": [{
            "timestamp": datetime.utcnow().isoformat(),
            "step": "escalated_to_human",
            "reason": determine_escalation_reason(state)
        }]
    }

# Resume endpoint (called by internal UI)
@app.post("/claims/{claim_id}/review-decision")
async def submit_review_decision(claim_id: str, decision: ReviewDecision):
    """Resume a paused claim graph with human decision."""
    config = {"configurable": {"thread_id": claim_id}}
    
    # Update state with human decision and resume
    await graph.aupdate_state(
        config,
        {
            "human_decision": decision.action,
            "human_reviewer_id": decision.reviewer_id,
            "audit_log": [{
                "timestamp": datetime.utcnow().isoformat(),
                "step": "human_decision_received",
                "decision": decision.action,
                "reviewer": decision.reviewer_id,
                "justification": decision.notes
            }]
        }
    )
    
    # Resume execution
    result = await graph.ainvoke(None, config)
    return {"status": "resumed", "result": result}
```

---

## Case Study 4: LlamaIndex Agents — Insurance Claims Pipeline with 15 Tools

### Architecture

```python
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool, QueryEngineTool
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.vector_stores.pinecone import PineconeVectorStore

# === DOCUMENT PROCESSING TOOLS (5) ===

def extract_claim_form(document_path: str) -> dict:
    """Extract structured data from insurance claim forms (PDF/image).
    Uses Azure Document Intelligence for high-accuracy extraction."""
    result = doc_intelligence_client.begin_analyze_document(
        "prebuilt-insurance-claim", document_path
    ).result()
    return {
        "claimant": result.fields["claimant_name"].value,
        "policy_number": result.fields["policy_number"].value,
        "incident_date": result.fields["incident_date"].value,
        "claimed_amount": result.fields["claimed_amount"].value,
        "description": result.fields["incident_description"].value
    }

def extract_medical_records(document_path: str) -> dict:
    """Extract diagnosis codes, treatment plans, and costs from medical records."""
    # Custom fine-tuned model for medical document extraction
    result = medical_extractor.process(document_path)
    return {
        "icd_codes": result.diagnosis_codes,
        "treatments": result.treatments,
        "total_billed": result.total_amount,
        "provider": result.provider_name
    }

def extract_police_report(document_path: str) -> dict:
    """Extract incident details from police reports."""
    pass  # Similar pattern

def extract_repair_estimate(document_path: str) -> dict:
    """Extract line items from auto repair estimates."""
    pass

def classify_document(document_path: str) -> str:
    """Classify document type: claim_form, medical_record, police_report, 
    repair_estimate, photo_evidence, correspondence."""
    pass

# === POLICY VERIFICATION TOOLS (3) ===

def lookup_policy(policy_number: str) -> dict:
    """Look up policy details including coverage limits, deductibles, exclusions."""
    policy = policy_db.get(policy_number)
    return {
        "holder": policy.holder_name,
        "type": policy.policy_type,
        "coverage_limit": policy.max_coverage,
        "deductible": policy.deductible,
        "exclusions": policy.exclusion_list,
        "status": policy.status,
        "effective_dates": {"start": policy.start_date, "end": policy.end_date}
    }

def check_coverage_applies(policy_number: str, incident_type: str, incident_date: str) -> dict:
    """Verify that the specific incident type is covered under the policy on the given date."""
    policy = policy_db.get(policy_number)
    is_covered = incident_type not in policy.exclusion_list
    is_active = policy.start_date <= incident_date <= policy.end_date
    return {
        "covered": is_covered and is_active,
        "reason": "Policy active and incident type covered" if (is_covered and is_active) 
                  else f"Excluded: {incident_type}" if not is_covered 
                  else "Policy not active on incident date"
    }

def get_claim_history(policy_number: str) -> list:
    """Get previous claims for this policy (fraud signal)."""
    return claims_db.get_history(policy_number)

# === FRAUD DETECTION TOOLS (3) ===

def run_fraud_model(claim_data: dict) -> dict:
    """Run ML fraud detection model on claim features."""
    features = featurize_claim(claim_data)
    score = fraud_model.predict_proba(features)[0][1]
    explanations = shap_explainer.explain(features)
    return {
        "fraud_probability": score,
        "risk_level": "high" if score > 0.7 else "medium" if score > 0.4 else "low",
        "top_risk_factors": explanations[:3]
    }

def check_watchlists(claimant_name: str, provider_name: str) -> dict:
    """Check claimant and provider against known fraud watchlists."""
    pass

def detect_duplicate_claim(claim_data: dict) -> dict:
    """Check for duplicate or overlapping claims."""
    pass

# === DECISION & COMMUNICATION TOOLS (4) ===

def calculate_payout(claimed_amount: float, deductible: float, coverage_limit: float, depreciation: float) -> dict:
    """Calculate approved payout amount based on policy terms."""
    net_claim = claimed_amount - deductible
    depreciated = net_claim * (1 - depreciation)
    approved = min(depreciated, coverage_limit)
    return {"approved_amount": approved, "calculation_breakdown": {...}}

def generate_decision_letter(claim_id: str, decision: str, amount: float, reasoning: str) -> str:
    """Generate formal decision letter (approval/denial) with regulatory-compliant language."""
    pass

def schedule_inspection(claim_id: str, inspection_type: str, preferred_dates: list) -> dict:
    """Schedule a physical inspection if required."""
    pass

def escalate_to_adjuster(claim_id: str, reason: str, priority: str) -> dict:
    """Escalate claim to human adjuster with full context package."""
    pass

# === RAG TOOL: Policy Manual Search ===

# Index over 2000+ pages of policy manuals, guidelines, and regulations
vector_store = PineconeVectorStore(index_name="policy-manuals")
policy_index = VectorStoreIndex.from_vector_store(vector_store)
policy_query_engine = policy_index.as_query_engine(similarity_top_k=5)

policy_manual_tool = QueryEngineTool.from_defaults(
    query_engine=policy_query_engine,
    name="policy_manual_search",
    description="Search internal policy manuals and state regulations for coverage rules, "
                "claim handling procedures, and compliance requirements."
)

# === AGENT ASSEMBLY ===

tools = [
    FunctionTool.from_defaults(fn=extract_claim_form),
    FunctionTool.from_defaults(fn=extract_medical_records),
    FunctionTool.from_defaults(fn=extract_police_report),
    FunctionTool.from_defaults(fn=extract_repair_estimate),
    FunctionTool.from_defaults(fn=classify_document),
    FunctionTool.from_defaults(fn=lookup_policy),
    FunctionTool.from_defaults(fn=check_coverage_applies),
    FunctionTool.from_defaults(fn=get_claim_history),
    FunctionTool.from_defaults(fn=run_fraud_model),
    FunctionTool.from_defaults(fn=check_watchlists),
    FunctionTool.from_defaults(fn=detect_duplicate_claim),
    FunctionTool.from_defaults(fn=calculate_payout),
    FunctionTool.from_defaults(fn=generate_decision_letter),
    FunctionTool.from_defaults(fn=schedule_inspection),
    policy_manual_tool
]

claims_agent = ReActAgent.from_tools(
    tools=tools,
    llm=OpenAI(model="gpt-4o", temperature=0),
    verbose=True,
    max_iterations=20,
    system_prompt="""You are an insurance claims processing agent. Process claims by:
    1. Classify and extract all submitted documents
    2. Verify policy coverage
    3. Run fraud checks
    4. Calculate payout if approved
    5. Generate decision letter or escalate if needed
    
    RULES:
    - Never approve a claim without verifying coverage first
    - Always run fraud detection before approval
    - Claims > $100K must be escalated regardless of fraud score
    - Document every decision with reasoning from policy manuals"""
)
```

### Production Lesson: Tool Selection Explosion

With 15 tools, the agent sometimes selected wrong tools or called them in suboptimal order. Solution:

```python
# Hierarchical tool selection: group tools into phases
# Agent sees 3-4 tools at a time, not all 15

phase_tools = {
    "extraction": [extract_claim_form, extract_medical_records, classify_document, ...],
    "verification": [lookup_policy, check_coverage_applies, get_claim_history, policy_manual_tool],
    "fraud_check": [run_fraud_model, check_watchlists, detect_duplicate_claim],
    "decision": [calculate_payout, generate_decision_letter, escalate_to_adjuster]
}

# Custom agent loop that restricts available tools per phase
class PhasedClaimsAgent:
    def __init__(self):
        self.current_phase = "extraction"
        
    def get_available_tools(self) -> list:
        return phase_tools[self.current_phase]
    
    def advance_phase(self, state: dict) -> str:
        if self.current_phase == "extraction" and state.get("documents_extracted"):
            return "verification"
        # ... phase transition logic
```

---

## Case Study 5: Migration War Story — LangChain to Custom Orchestration

### The Setup

**Company:** DataSift Analytics (Series A, 20 engineers)
**Initial choice:** LangChain (seemed like the obvious default in early 2024)
**System:** Data analysis agent that connects to customer databases, writes SQL, generates visualizations

### What Went Wrong (Months 1-4)

**Month 1: Rapid prototyping (things look great)**
```python
# Initial LangChain implementation — beautiful simplicity
from langchain.agents import create_sql_agent
from langchain.sql_database import SQLDatabase

db = SQLDatabase.from_uri(customer_db_url)
agent = create_sql_agent(llm, db=db, verbose=True)
result = agent.run("What were our top 10 customers by revenue last quarter?")
# Works! Ship it!
```

**Month 2: First production issues**
```python
# Problem: LangChain's abstraction layers made debugging impossible
# When the agent generated wrong SQL, the error trace was:
#   langchain.agents.agent.AgentExecutor._call()
#   → langchain.agents.mrkl.base.ZeroShotAgent.plan()
#   → langchain.chains.llm.LLMChain._call()
#   → langchain.llms.openai.OpenAI._generate()
# 
# 5 abstraction layers to find: the prompt template had a typo

# Problem: Version instability
# langchain==0.1.4 → 0.1.5 broke SQLDatabaseChain API
# langchain==0.1.7 moved sql_database to langchain_community
# langchain==0.1.12 deprecated AgentExecutor in favor of langgraph
```

**Month 3: Scaling issues**
```python
# Problem: Memory usage
# LangChain's ConversationBufferMemory kept ENTIRE conversation in memory
# Customer with 50-message session = 200KB of context per request
# 1000 concurrent sessions = 200MB just in conversation buffers
# Plus LangChain objects are not pickle-able → can't offload to Redis easily

# Problem: Latency
# Simple tool call path in LangChain:
# 1. AgentExecutor formats prompt (string manipulation) — 2ms
# 2. Passes through OutputParser — 1ms  
# 3. Goes through CallbackManager (even with no callbacks) — 5ms
# 4. LLM call — 800ms
# 5. OutputParser parses response — 3ms
# 6. ToolExecutor looks up tool — 1ms
# 7. Tool runs — variable
#
# Overhead per tool call: ~12ms
# Agent averaging 6 tool calls: 72ms overhead
# Not terrible, but unnecessary
```

**Month 4: The breaking point**
```python
# Customer request: "I need the agent to try a SQL query, and if it fails,
# modify it up to 3 times. If all retries fail, ask the user for clarification."
#
# In LangChain, this required:
# 1. Custom AgentExecutor subclass (fighting the framework)
# 2. Custom OutputParser to detect SQL errors
# 3. Custom Tool wrapper with retry logic
# 4. Custom Memory class to track retry state
#
# Total: 400 lines of framework-fighting code for a 30-line feature
```

### The Migration (2 Weeks)

```python
# The custom orchestration that replaced LangChain
# Total: 180 lines of core orchestration code

import openai
import json
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class AgentState:
    messages: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3

class SimpleAgent:
    def __init__(self, model: str, tools: dict[str, Callable], system_prompt: str):
        self.client = openai.OpenAI()
        self.model = model
        self.tools = tools
        self.system_prompt = system_prompt
        self.tool_schemas = [self._make_schema(name, fn) for name, fn in tools.items()]
    
    async def run(self, user_input: str, state: AgentState = None) -> str:
        state = state or AgentState()
        state.messages.append({"role": "user", "content": user_input})
        
        while True:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": self.system_prompt}] + state.messages,
                tools=self.tool_schemas if self.tools else None
            )
            
            msg = response.choices[0].message
            
            # No tool calls → final response
            if not msg.tool_calls:
                state.messages.append({"role": "assistant", "content": msg.content})
                return msg.content
            
            # Process tool calls
            state.messages.append(msg.model_dump())
            for tool_call in msg.tool_calls:
                result = await self._execute_tool(tool_call, state)
                state.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result)
                })
    
    async def _execute_tool(self, tool_call, state: AgentState) -> dict:
        fn = self.tools[tool_call.function.name]
        args = json.loads(tool_call.function.arguments)
        try:
            return {"success": True, "result": await fn(**args)}
        except Exception as e:
            state.retry_count += 1
            return {"success": False, "error": str(e), "retry": state.retry_count}
```

### Results After Migration

| Metric | LangChain | Custom | Improvement |
|--------|-----------|--------|-------------|
| P50 latency | 1.2s | 0.9s | 25% faster |
| P99 latency | 4.8s | 2.1s | 56% faster |
| Memory per session | 200KB | 45KB | 77% less |
| Lines of orchestration code | 1,200 | 180 | 85% less |
| Time to add new feature | 2-3 days | 2-4 hours | 90% faster |
| Dependency vulnerabilities | 12 (transitive) | 1 (openai) | 92% fewer |

---

## Case Study 6: When NOT to Use a Framework

### Scenario: Simple RAG Chatbot

A team spent 3 weeks implementing a RAG chatbot with LangChain. The entire useful logic:

```python
# What they actually needed (40 lines):
import openai
from pinecone import Pinecone

client = openai.OpenAI()
pc = Pinecone()
index = pc.Index("knowledge-base")

def chat(user_message: str, history: list[dict]) -> str:
    # 1. Embed the query
    embedding = client.embeddings.create(input=user_message, model="text-embedding-3-small")
    
    # 2. Search vector store
    results = index.query(vector=embedding.data[0].embedding, top_k=5, include_metadata=True)
    context = "\n".join([r.metadata["text"] for r in results.matches])
    
    # 3. Generate response
    messages = [
        {"role": "system", "content": f"Answer using this context:\n{context}"},
        *history,
        {"role": "user", "content": user_message}
    ]
    response = client.chat.completions.create(model="gpt-4o-mini", messages=messages)
    return response.choices[0].message.content
```

**What LangChain added:** 15 files, 800 lines, RetrievalQA chain, ConversationalRetrievalChain, custom document loaders, output parsers, callback handlers. All to do exactly what 40 lines of direct code does.

### Rule of Thumb: Use a Framework When...

| Condition | Framework? | Why |
|-----------|-----------|-----|
| Linear tool-calling loop | No | Direct OpenAI function calling suffices |
| Complex state machine with branching | Yes (LangGraph) | State management is genuinely hard |
| Multi-agent with handoffs | Yes (Agents SDK/LangGraph) | Coordination protocols matter |
| Simple RAG | No | Embedding + search + generate is trivial |
| Need human-in-the-loop with persistence | Yes (LangGraph) | Checkpointing is hard to build correctly |
| Prototype/hackathon | Maybe (LangChain) | Speed of initial development |
| Production with SLA | Depends | Framework must not be the bottleneck |

---

## Case Study 7: Performance Benchmarks

### Test Setup

**Task:** "Look up the weather in 3 cities, then summarize the results"
**LLM:** GPT-4o (same for all frameworks)
**Infrastructure:** Single m5.xlarge EC2 instance
**Measurement:** 100 runs each, reporting P50/P95/P99

### Results

| Framework | P50 (ms) | P95 (ms) | P99 (ms) | Overhead vs Raw | Memory (MB) |
|-----------|----------|----------|----------|-----------------|-------------|
| Raw OpenAI SDK | 1,842 | 2,310 | 2,890 | baseline | 34 |
| OpenAI Agents SDK | 1,891 | 2,380 | 2,950 | +2.7% | 41 |
| LangGraph | 1,920 | 2,520 | 3,210 | +4.2% | 68 |
| LangChain AgentExecutor | 1,980 | 2,840 | 3,890 | +7.5% | 112 |
| CrewAI | 2,340 | 3,680 | 5,120 | +27% | 156 |
| AutoGen | 2,180 | 3,240 | 4,560 | +18% | 134 |

**Key insight:** For simple tasks, framework overhead is noise compared to LLM latency. CrewAI's overhead comes from its internal agent-to-agent messaging. The difference matters at scale (10K+ requests/hour) or for latency-sensitive applications.

### Where Frameworks Win on Performance

For complex multi-step tasks (10+ tool calls with branching):

| Framework | Correct completion rate | Avg tool calls | Wasted LLM calls |
|-----------|----------------------|----------------|-------------------|
| Raw (manual) | 72% | 14.2 | 3.8 |
| LangGraph | 91% | 11.3 | 1.2 |
| OpenAI Agents SDK | 88% | 11.8 | 1.5 |

Frameworks reduce wasted LLM calls through better prompting, state management, and error recovery — saving more in LLM costs than they add in overhead.

---

## Case Study 8: Framework Lock-in Risks and Mitigation

### The Anti-Pattern: Framework-Coupled Business Logic

```python
# BAD: Business logic embedded in LangGraph nodes
from langgraph.graph import StateGraph

def process_order(state):
    # Business logic tangled with framework state management
    if state["order_total"] > 1000:
        state["requires_approval"] = True
        state["approval_level"] = "manager" if state["order_total"] < 5000 else "director"
    # This logic is now untestable without LangGraph
    return state
```

### The Solution: Hexagonal Architecture for Agents

```python
# GOOD: Framework-agnostic core with thin framework adapter

# === Core Domain (zero framework dependencies) ===
@dataclass
class Order:
    total: float
    items: list[str]
    customer_tier: str

class OrderApprovalPolicy:
    def requires_approval(self, order: Order) -> bool:
        return order.total > 1000
    
    def approval_level(self, order: Order) -> str:
        if order.total < 5000:
            return "manager"
        return "director"

class OrderProcessor:
    def __init__(self, policy: OrderApprovalPolicy, inventory: InventoryPort):
        self.policy = policy
        self.inventory = inventory
    
    def process(self, order: Order) -> ProcessingResult:
        if self.policy.requires_approval(order):
            return ProcessingResult(status="pending_approval", 
                                    level=self.policy.approval_level(order))
        return ProcessingResult(status="approved")

# === LangGraph Adapter (thin wrapper) ===
def langgraph_process_order(state: dict) -> dict:
    processor = OrderProcessor(OrderApprovalPolicy(), inventory_adapter)
    order = Order(**state["order_data"])
    result = processor.process(order)
    return {"processing_result": asdict(result)}

# === Could also be OpenAI Agents SDK adapter ===
@function_tool
def agents_sdk_process_order(order_total: float, items: list[str], customer_tier: str) -> str:
    processor = OrderProcessor(OrderApprovalPolicy(), inventory_adapter)
    order = Order(total=order_total, items=items, customer_tier=customer_tier)
    result = processor.process(order)
    return json.dumps(asdict(result))
```

---

## Case Study 9: Multi-Framework Architecture

### Real Production System: Enterprise Knowledge Assistant

```
┌─────────────────────────────────────────────────────────┐
│                    User Request                          │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│          LangGraph: Orchestration Layer                  │
│  - Workflow state management                            │
│  - Human-in-the-loop gates                             │
│  - Checkpoint/resume                                    │
│  - Routing decisions                                    │
└───────┬──────────────┬──────────────────┬───────────────┘
        │              │                  │
        ▼              ▼                  ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐
│  LlamaIndex  │ │   Custom     │ │  OpenAI Agents SDK   │
│  Retrieval   │ │   Tools      │ │  Sub-agents          │
│              │ │              │ │                      │
│ - Vector     │ │ - DB queries │ │ - Summarizer agent   │
│   search     │ │ - API calls  │ │ - Analyst agent      │
│ - Reranking  │ │ - File ops   │ │ - Writer agent       │
│ - Hybrid     │ │ - Compute    │ │                      │
│   retrieval  │ │              │ │                      │
└──────────────┘ └──────────────┘ └──────────────────────┘
```

```python
# Orchestration layer: LangGraph manages the workflow
from langgraph.graph import StateGraph

# Retrieval layer: LlamaIndex handles document search
from llama_index.core import VectorStoreIndex
from llama_index.core.postprocessor import CohereRerank

# Sub-agent layer: OpenAI Agents SDK for specialized tasks  
from agents import Agent, Runner

class KnowledgeAssistantState(TypedDict):
    query: str
    retrieved_context: list[str]
    analysis: str
    final_response: str
    confidence: float

async def retrieve_context(state: KnowledgeAssistantState) -> dict:
    """LlamaIndex handles retrieval with reranking."""
    query_engine = index.as_query_engine(
        similarity_top_k=20,
        node_postprocessors=[CohereRerank(top_n=5)]
    )
    response = await query_engine.aquery(state["query"])
    return {"retrieved_context": [node.text for node in response.source_nodes]}

async def analyze_with_specialist(state: KnowledgeAssistantState) -> dict:
    """OpenAI Agents SDK runs specialist analysis."""
    analyst = Agent(
        name="Analyst",
        instructions="Analyze the provided context and extract key insights relevant to the query.",
        model="gpt-4o"
    )
    result = await Runner.run(
        analyst, 
        input=f"Query: {state['query']}\nContext: {state['retrieved_context']}"
    )
    return {"analysis": result.final_output}

async def execute_custom_tools(state: KnowledgeAssistantState) -> dict:
    """Plain Python for deterministic operations."""
    # No framework needed for: database lookups, calculations, API calls
    metrics = await metrics_db.query(state["query"])
    return {"retrieved_context": state["retrieved_context"] + [json.dumps(metrics)]}
```

---

## Case Study 10: Production Gotchas

### Memory Leaks in LangGraph

```python
# GOTCHA: Accumulated state in long-running graphs
# Each checkpoint stores full state. If state grows unboundedly:

class BadState(TypedDict):
    messages: Annotated[list, operator.add]  # GROWS FOREVER
    all_tool_results: Annotated[list, operator.add]  # GROWS FOREVER

# After 100 turns: state = 2MB per checkpoint × 100 checkpoints = 200MB per thread

# FIX: Sliding window + summarization
class GoodState(TypedDict):
    recent_messages: list  # Keep last 10 only
    conversation_summary: str  # Summarize older messages
    current_tool_result: dict  # Only current, not historical
```

### State Corruption in CrewAI

```python
# GOTCHA: CrewAI agents share mutable state without isolation
# Two agents running "concurrently" can corrupt shared context

# This actually happened in production:
# Agent A reads customer_balance = $500
# Agent B processes a refund, updates balance to $600
# Agent A (still on old read) approves a $500 charge
# Customer now has -$400 balance (should be $100)

# FIX: Don't use CrewAI for stateful financial operations
# Use LangGraph with explicit state transitions instead
```

### Error Recovery Patterns

```python
# LangGraph: Retry with exponential backoff at node level
def create_resilient_node(fn, max_retries=3):
    async def wrapper(state):
        for attempt in range(max_retries):
            try:
                return await fn(state)
            except RateLimitError:
                await asyncio.sleep(2 ** attempt)
            except ToolExecutionError as e:
                # Record error in state, let graph decide next step
                return {"last_error": str(e), "error_count": state.get("error_count", 0) + 1}
        # All retries exhausted → escalate
        return {"requires_human_review": True, "escalation_reason": "tool_failure"}
    return wrapper

# OpenAI Agents SDK: Built-in retry via RunConfig
from agents import RunConfig

config = RunConfig(
    max_turns=15,
    # No built-in retry — wrap tools yourself
)

# Production pattern: Circuit breaker for external tools
class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failures = 0
        self.threshold = failure_threshold
        self.last_failure = None
        self.timeout = recovery_timeout
    
    async def call(self, fn, *args):
        if self.failures >= self.threshold:
            if time.time() - self.last_failure < self.timeout:
                raise CircuitOpenError("Tool circuit breaker is open")
            self.failures = 0  # Try again
        
        try:
            result = await fn(*args)
            self.failures = 0
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure = time.time()
            raise
```

### The #1 Production Gotcha Across All Frameworks

**Token accumulation in agent loops.** Every framework suffers from this:

```python
# Agent makes 8 tool calls. Each call adds to message history.
# By call #8, the prompt is:
#   System prompt: 500 tokens
#   User message: 100 tokens  
#   Tool call 1 + result: 300 tokens
#   Tool call 2 + result: 450 tokens
#   ...
#   Tool call 7 + result: 600 tokens
#   TOTAL: 4,500 tokens input per call
#
# Cost for 8 calls: 4,500 × 8 / 2 (average) = 18,000 input tokens
# At GPT-4o pricing: $0.045 per conversation
# At 10K conversations/day: $450/day just for input tokens

# FIX: Sliding context window
def trim_tool_history(messages: list, max_tool_results: int = 3) -> list:
    """Keep only the N most recent tool results in context."""
    tool_messages = [m for m in messages if m["role"] == "tool"]
    if len(tool_messages) <= max_tool_results:
        return messages
    
    # Summarize old tool results into a single message
    old_results = tool_messages[:-max_tool_results]
    summary = f"Previous tool calls summary: {summarize(old_results)}"
    
    # Reconstruct message list with summary
    return [messages[0], {"role": "system", "content": summary}] + messages[-max_tool_results*2:]
```

---

## Summary: Decision Framework

```
Need persistent state + human-in-the-loop?     → LangGraph
Need multi-agent handoffs with tracing?         → OpenAI Agents SDK
Need document-heavy RAG with many tools?        → LlamaIndex
Need quick prototype/demo?                      → LangChain or CrewAI
Need maximum control + minimal overhead?        → Custom orchestration
Need all of the above?                          → Multi-framework (this is common)
```

The best teams treat frameworks as interchangeable infrastructure layers, not as architectural commitments. Keep business logic framework-agnostic, and you'll never be locked in.
