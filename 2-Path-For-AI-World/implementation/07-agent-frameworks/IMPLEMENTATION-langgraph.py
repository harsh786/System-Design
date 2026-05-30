"""
LangGraph Implementation - Production Agent with Full Features
==============================================================

Demonstrates:
- Typed state management
- Tool-calling agent node
- Conditional routing
- Human-in-the-loop approval
- Persistence (SQLite checkpointer)
- Subgraph composition
- Parallel branch execution
- Error handling and retry
- Streaming output
"""

from __future__ import annotations

import asyncio
import json
import operator
import os
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal, Optional, Sequence, TypedDict

# LangGraph imports
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command, interrupt

# LangChain imports for LLM and tools
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI


# =============================================================================
# 1. STATE DEFINITION
# =============================================================================

class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class AgentState(TypedDict):
    """
    The state that flows through the entire graph.
    
    Using Annotated with operator.add for messages means new messages
    are APPENDED rather than replacing the list.
    """
    # Core conversation
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # Agent routing
    next_action: str
    
    # Human-in-the-loop
    requires_approval: bool
    approval_status: ApprovalStatus
    approval_reason: str
    
    # Metadata
    iteration_count: int
    max_iterations: int
    errors: Annotated[list[str], operator.add]
    
    # Results from parallel branches
    research_results: dict[str, Any]
    analysis_results: dict[str, Any]
    
    # Final output
    final_answer: str


# =============================================================================
# 2. TOOL DEFINITIONS
# =============================================================================

@tool
def search_web(query: str) -> str:
    """Search the web for information. Use for current events or factual queries."""
    # Simulated - in production, use actual search API
    return f"Search results for '{query}': [Simulated results - integrate with Tavily/Serper/etc]"


@tool
def query_database(sql: str) -> str:
    """Execute a SQL query against the analytics database. Use for data questions."""
    # Simulated - in production, use actual DB connection
    if "DROP" in sql.upper() or "DELETE" in sql.upper():
        return "ERROR: Destructive queries are not allowed."
    return f"Query results for: {sql}\n[Simulated: 42 rows returned]"


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email. REQUIRES HUMAN APPROVAL before execution."""
    return f"Email sent to {to} with subject '{subject}'"


@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression safely."""
    try:
        # In production, use a safe math parser
        allowed_chars = set("0123456789+-*/.() ")
        if all(c in allowed_chars for c in expression):
            result = eval(expression)  # Safe due to char restriction
            return f"Result: {result}"
        return "ERROR: Invalid characters in expression"
    except Exception as e:
        return f"ERROR: {str(e)}"


# Tools that require approval before execution
APPROVAL_REQUIRED_TOOLS = {"send_email"}

# All tools
ALL_TOOLS = [search_web, query_database, send_email, calculate]


# =============================================================================
# 3. NODE FUNCTIONS
# =============================================================================

def create_agent_node(model: ChatOpenAI):
    """Create the main agent node that decides what to do next."""
    
    async def agent_node(state: AgentState) -> dict:
        """Main agent reasoning node."""
        system_prompt = SystemMessage(content="""You are a helpful AI assistant with access to tools.
        
Rules:
- Use tools when needed to answer questions
- For emails or actions with side effects, always confirm with the user first
- Be concise and accurate
- If you don't know something, say so
- Cite your sources when using search results
""")
        
        messages = [system_prompt] + list(state["messages"])
        
        # Bind tools to model
        model_with_tools = model.bind_tools(ALL_TOOLS)
        
        response = await model_with_tools.ainvoke(messages)
        
        # Check if any tool calls require approval
        requires_approval = False
        if response.tool_calls:
            for tc in response.tool_calls:
                if tc["name"] in APPROVAL_REQUIRED_TOOLS:
                    requires_approval = True
                    break
        
        return {
            "messages": [response],
            "requires_approval": requires_approval,
            "iteration_count": state.get("iteration_count", 0) + 1,
        }
    
    return agent_node


async def tool_executor_node(state: AgentState) -> dict:
    """Execute tools that don't require approval."""
    tool_node = ToolNode(tools=ALL_TOOLS)
    result = await tool_node.ainvoke(state)
    return result


async def human_approval_node(state: AgentState) -> dict:
    """
    Human-in-the-loop approval node.
    
    This uses LangGraph's interrupt() to pause execution
    and wait for human input.
    """
    last_message = state["messages"][-1]
    
    # Format the approval request
    tool_calls_desc = []
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        for tc in last_message.tool_calls:
            tool_calls_desc.append(
                f"  Tool: {tc['name']}\n  Args: {json.dumps(tc['args'], indent=2)}"
            )
    
    approval_request = (
        "The agent wants to perform the following action(s):\n"
        + "\n".join(tool_calls_desc)
        + "\n\nDo you approve? (yes/no)"
    )
    
    # This pauses the graph and waits for human input
    human_response = interrupt({"question": approval_request})
    
    if human_response.lower() in ("yes", "y", "approve"):
        return {
            "approval_status": ApprovalStatus.APPROVED,
            "approval_reason": "Human approved",
        }
    else:
        # Rejected - add a message telling the agent
        rejection_messages = []
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            for tc in last_message.tool_calls:
                rejection_messages.append(
                    ToolMessage(
                        content=f"REJECTED: Human denied execution of {tc['name']}. Reason: {human_response}",
                        tool_call_id=tc["id"],
                    )
                )
        
        return {
            "messages": rejection_messages,
            "approval_status": ApprovalStatus.REJECTED,
            "approval_reason": human_response,
        }


async def error_handler_node(state: AgentState) -> dict:
    """Handle errors and decide whether to retry or fail gracefully."""
    errors = state.get("errors", [])
    iteration_count = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 10)
    
    if iteration_count >= max_iterations:
        return {
            "final_answer": f"I was unable to complete the task after {max_iterations} attempts. Errors encountered: {'; '.join(errors[-3:])}",
            "next_action": "end",
        }
    
    # Add a retry message
    return {
        "messages": [
            HumanMessage(content="The previous attempt had an error. Please try a different approach.")
        ],
        "next_action": "retry",
    }


async def synthesize_node(state: AgentState) -> dict:
    """Synthesize results from parallel branches into final answer."""
    research = state.get("research_results", {})
    analysis = state.get("analysis_results", {})
    
    synthesis = f"""
Based on my research and analysis:

Research Findings:
{json.dumps(research, indent=2) if research else "No research conducted"}

Analysis Results:
{json.dumps(analysis, indent=2) if analysis else "No analysis conducted"}
"""
    return {
        "final_answer": synthesis,
        "messages": [AIMessage(content=synthesis)],
    }


# =============================================================================
# 4. CONDITIONAL EDGES (ROUTING)
# =============================================================================

def route_after_agent(state: AgentState) -> str:
    """Route based on agent's output."""
    last_message = state["messages"][-1]
    
    # Check iteration limit
    if state.get("iteration_count", 0) >= state.get("max_iterations", 10):
        return "error_handler"
    
    # If no tool calls, agent is done
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return "end"
    
    # If tool calls require approval, go to human
    if state.get("requires_approval", False):
        return "human_approval"
    
    # Otherwise execute tools
    return "tools"


def route_after_approval(state: AgentState) -> str:
    """Route based on human approval decision."""
    if state.get("approval_status") == ApprovalStatus.APPROVED:
        return "tools"
    else:
        return "agent"  # Go back to agent with rejection info


# =============================================================================
# 5. SUBGRAPH - Research Branch
# =============================================================================

class ResearchState(TypedDict):
    """State for the research subgraph."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    query: str
    results: dict[str, Any]


async def research_node(state: ResearchState) -> dict:
    """Perform research using search tools."""
    query = state.get("query", "")
    # Simulated research
    results = {
        "sources": [f"Source for: {query}"],
        "summary": f"Research summary for: {query}",
        "confidence": 0.85,
        "timestamp": datetime.now().isoformat(),
    }
    return {"results": results}


def build_research_subgraph() -> StateGraph:
    """Build a research subgraph that can be composed into the main graph."""
    builder = StateGraph(ResearchState)
    builder.add_node("research", research_node)
    builder.add_edge(START, "research")
    builder.add_edge("research", END)
    return builder.compile()


# =============================================================================
# 6. SUBGRAPH - Analysis Branch
# =============================================================================

class AnalysisState(TypedDict):
    """State for the analysis subgraph."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    data: str
    results: dict[str, Any]


async def analysis_node(state: AnalysisState) -> dict:
    """Perform data analysis."""
    data = state.get("data", "")
    results = {
        "metrics": {"count": 42, "average": 3.14},
        "insights": [f"Key insight from: {data}"],
        "timestamp": datetime.now().isoformat(),
    }
    return {"results": results}


def build_analysis_subgraph() -> StateGraph:
    """Build an analysis subgraph."""
    builder = StateGraph(AnalysisState)
    builder.add_node("analyze", analysis_node)
    builder.add_edge(START, "analyze")
    builder.add_edge("analyze", END)
    return builder.compile()


# =============================================================================
# 7. PARALLEL BRANCH EXECUTION
# =============================================================================

async def parallel_dispatch_node(state: AgentState) -> dict:
    """Dispatch parallel research and analysis branches."""
    # In LangGraph, parallel execution is done via Send() API
    # or by structuring the graph with fan-out/fan-in patterns
    
    research_subgraph = build_research_subgraph()
    analysis_subgraph = build_analysis_subgraph()
    
    # Execute in parallel
    research_task = asyncio.create_task(
        research_subgraph.ainvoke({"query": "latest market trends", "messages": []})
    )
    analysis_task = asyncio.create_task(
        analysis_subgraph.ainvoke({"data": "Q4 revenue data", "messages": []})
    )
    
    research_result, analysis_result = await asyncio.gather(research_task, analysis_task)
    
    return {
        "research_results": research_result.get("results", {}),
        "analysis_results": analysis_result.get("results", {}),
    }


# =============================================================================
# 8. GRAPH CONSTRUCTION
# =============================================================================

def build_main_graph(model: ChatOpenAI) -> StateGraph:
    """
    Build the main agent graph with all features.
    
    Graph structure:
    
    START → agent → [routing] → tools → agent (loop)
                              → human_approval → [routing] → tools / agent
                              → error_handler → [routing] → agent / END
                              → END (no tool calls = done)
    """
    builder = StateGraph(AgentState)
    
    # Add nodes
    builder.add_node("agent", create_agent_node(model))
    builder.add_node("tools", tool_executor_node)
    builder.add_node("human_approval", human_approval_node)
    builder.add_node("error_handler", error_handler_node)
    builder.add_node("parallel_research", parallel_dispatch_node)
    builder.add_node("synthesize", synthesize_node)
    
    # Entry point
    builder.add_edge(START, "agent")
    
    # Agent routing (conditional)
    builder.add_conditional_edges(
        "agent",
        route_after_agent,
        {
            "tools": "tools",
            "human_approval": "human_approval",
            "error_handler": "error_handler",
            "end": END,
        },
    )
    
    # After tools, go back to agent
    builder.add_edge("tools", "agent")
    
    # After human approval
    builder.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {
            "tools": "tools",
            "agent": "agent",
        },
    )
    
    # Error handler routing
    builder.add_conditional_edges(
        "error_handler",
        lambda state: state.get("next_action", "end"),
        {
            "retry": "agent",
            "end": END,
        },
    )
    
    # Parallel research branch (triggered explicitly)
    builder.add_edge("parallel_research", "synthesize")
    builder.add_edge("synthesize", END)
    
    return builder


# =============================================================================
# 9. PERSISTENCE & CHECKPOINTING
# =============================================================================

async def create_persistent_graph():
    """Create graph with SQLite persistence for durable execution."""
    model = ChatOpenAI(model="gpt-4o", temperature=0)
    
    # Build the graph
    graph_builder = build_main_graph(model)
    
    # Add SQLite checkpointer for persistence
    # This allows resuming from any checkpoint after crashes/restarts
    async with AsyncSqliteSaver.from_conn_string("checkpoints.db") as checkpointer:
        graph = graph_builder.compile(
            checkpointer=checkpointer,
            # interrupt_before=["human_approval"],  # Alternative: interrupt before node
        )
        yield graph


# =============================================================================
# 10. STREAMING OUTPUT
# =============================================================================

async def stream_agent_execution(graph, user_input: str, thread_id: str):
    """Stream agent execution with real-time updates."""
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 25,
    }
    
    initial_state = {
        "messages": [HumanMessage(content=user_input)],
        "requires_approval": False,
        "approval_status": ApprovalStatus.PENDING,
        "approval_reason": "",
        "iteration_count": 0,
        "max_iterations": 10,
        "errors": [],
        "research_results": {},
        "analysis_results": {},
        "final_answer": "",
        "next_action": "",
    }
    
    print(f"\n{'='*60}")
    print(f"User: {user_input}")
    print(f"{'='*60}\n")
    
    # Stream events
    async for event in graph.astream_events(initial_state, config, version="v2"):
        kind = event["event"]
        
        if kind == "on_chat_model_stream":
            # Stream LLM tokens as they arrive
            content = event["data"]["chunk"].content
            if content:
                print(content, end="", flush=True)
        
        elif kind == "on_tool_start":
            tool_name = event["name"]
            print(f"\n  🔧 Calling tool: {tool_name}")
        
        elif kind == "on_tool_end":
            tool_output = event["data"].get("output", "")
            print(f"  ✓ Tool result: {tool_output[:100]}...")
        
        elif kind == "on_chain_start" and event["name"] in ("agent", "tools", "human_approval"):
            print(f"\n  → Entering node: {event['name']}")
    
    print(f"\n{'='*60}\n")


# =============================================================================
# 11. FULL WORKING EXAMPLE
# =============================================================================

async def main():
    """Run the full agent example."""
    
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY environment variable to run this example.")
        print("Showing graph structure instead...\n")
        
        # Show graph structure without running
        model = ChatOpenAI(model="gpt-4o", temperature=0)
        graph_builder = build_main_graph(model)
        graph = graph_builder.compile()
        
        # Print graph visualization
        print("Graph nodes:", list(graph.nodes.keys()))
        print("\nGraph structure (Mermaid):")
        print(graph.get_graph().draw_mermaid())
        return
    
    # Create model
    model = ChatOpenAI(model="gpt-4o", temperature=0, streaming=True)
    
    # Build graph with persistence
    graph_builder = build_main_graph(model)
    
    async with AsyncSqliteSaver.from_conn_string("checkpoints.db") as checkpointer:
        graph = graph_builder.compile(checkpointer=checkpointer)
        
        # Example 1: Simple tool use
        await stream_agent_execution(
            graph,
            "What is 42 * 17 + 3?",
            thread_id="thread-1",
        )
        
        # Example 2: Search (would trigger web search tool)
        await stream_agent_execution(
            graph,
            "Search for the latest developments in AI agent frameworks",
            thread_id="thread-2",
        )
        
        # Example 3: Action requiring approval (email)
        # This would pause at human_approval node
        await stream_agent_execution(
            graph,
            "Send an email to team@company.com summarizing Q4 results",
            thread_id="thread-3",
        )


# =============================================================================
# 12. RETRY WITH EXPONENTIAL BACKOFF NODE
# =============================================================================

class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0


async def retry_wrapper_node(state: AgentState) -> dict:
    """
    Wraps tool execution with retry logic.
    Useful for flaky external APIs.
    """
    config = RetryConfig()
    last_error = None
    
    for attempt in range(config.max_retries):
        try:
            result = await tool_executor_node(state)
            return result
        except Exception as e:
            last_error = str(e)
            delay = min(
                config.base_delay * (config.exponential_base ** attempt),
                config.max_delay,
            )
            await asyncio.sleep(delay)
    
    return {
        "errors": [f"Tool execution failed after {config.max_retries} retries: {last_error}"],
        "messages": [
            ToolMessage(
                content=f"ERROR: Tool execution failed: {last_error}",
                tool_call_id=state["messages"][-1].tool_calls[0]["id"]
                if state["messages"][-1].tool_calls
                else "unknown",
            )
        ],
    }


# =============================================================================
# 13. TESTING UTILITIES
# =============================================================================

async def test_graph_deterministic():
    """
    Test the graph with deterministic (mocked) LLM responses.
    Critical for CI/CD pipelines.
    """
    from unittest.mock import AsyncMock, patch
    
    model = ChatOpenAI(model="gpt-4o", temperature=0)
    graph_builder = build_main_graph(model)
    graph = graph_builder.compile()
    
    # Mock the LLM to return a predictable response
    mock_response = AIMessage(
        content="The answer is 717.",
        tool_calls=[],  # No tool calls = agent is done
    )
    
    with patch.object(ChatOpenAI, "ainvoke", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_response
        
        result = await graph.ainvoke({
            "messages": [HumanMessage(content="What is 42 * 17 + 3?")],
            "requires_approval": False,
            "approval_status": ApprovalStatus.PENDING,
            "approval_reason": "",
            "iteration_count": 0,
            "max_iterations": 10,
            "errors": [],
            "research_results": {},
            "analysis_results": {},
            "final_answer": "",
            "next_action": "",
        })
        
        # Verify
        assert len(result["messages"]) >= 2  # Input + response
        print("✓ Deterministic test passed")


if __name__ == "__main__":
    asyncio.run(main())
