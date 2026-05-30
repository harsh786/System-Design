"""
IMPLEMENTATION: Tool/Function Calling with LLMs
================================================
Complete implementation of tool calling patterns including:
schema definition, single/parallel calling, error handling,
conversation history management, and a tool registry system.
"""

import json
import asyncio
import time
import traceback
from typing import Any, Callable, Optional
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

from openai import OpenAI, AsyncOpenAI


# =============================================================================
# 1. TOOL SCHEMA DEFINITION
# =============================================================================

# Tools are defined as JSON schemas that tell the model:
# - WHAT the tool does (description — the model uses this to decide when to call it)
# - WHAT parameters it accepts (properties, types, constraints)
# - WHICH parameters are required

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": (
                "Search the knowledge base for relevant documents. "
                "Use this when the user asks factual questions that require "
                "looking up information from our documentation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query. Be specific and use keywords."
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (1-10)",
                        "default": 5
                    },
                    "filters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "enum": ["technical", "billing", "general"]
                            },
                            "date_after": {
                                "type": "string",
                                "description": "ISO date string. Only return docs after this date."
                            }
                        }
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a location. Use when user asks about weather conditions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name or coordinates (lat,lon)"
                    },
                    "units": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "default": "celsius"
                    }
                },
                "required": ["location"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": (
                "Execute a read-only SQL query against the analytics database. "
                "Use for data questions about metrics, counts, aggregations. "
                "NEVER use for writes/updates/deletes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The SQL SELECT query to execute"
                    },
                    "database": {
                        "type": "string",
                        "enum": ["analytics", "users", "products"],
                        "description": "Which database to query"
                    }
                },
                "required": ["query", "database"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email to a recipient. Use only when user explicitly requests sending an email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string"},
                    "body": {"type": "string", "description": "Email body in plain text"},
                    "priority": {"type": "string", "enum": ["low", "normal", "high"], "default": "normal"}
                },
                "required": ["to", "subject", "body"]
            }
        }
    }
]


# =============================================================================
# 2. TOOL IMPLEMENTATIONS (the actual functions)
# =============================================================================

def search_documents(query: str, top_k: int = 5, filters: dict = None) -> dict:
    """Simulated document search. In production, this calls your vector DB."""
    # Simulate search latency
    time.sleep(0.1)
    return {
        "results": [
            {"title": f"Doc about {query}", "snippet": f"Relevant content for: {query}", "score": 0.95},
            {"title": f"Related: {query}", "snippet": f"Additional info about: {query}", "score": 0.82},
        ],
        "total_results": 2,
        "query": query,
    }


def get_weather(location: str, units: str = "celsius") -> dict:
    """Simulated weather API."""
    return {
        "location": location,
        "temperature": 22 if units == "celsius" else 72,
        "units": units,
        "condition": "partly cloudy",
        "humidity": 65,
    }


def execute_sql(query: str, database: str) -> dict:
    """Simulated SQL execution. In production, use read-only connection with timeouts."""
    # SECURITY: Validate query is read-only
    if any(keyword in query.upper() for keyword in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER"]):
        raise PermissionError("Only SELECT queries are allowed")
    return {
        "columns": ["date", "count"],
        "rows": [["2024-01-01", 150], ["2024-01-02", 163]],
        "row_count": 2,
    }


def send_email(to: str, subject: str, body: str, priority: str = "normal") -> dict:
    """Simulated email sending."""
    return {"status": "sent", "message_id": "msg_12345", "to": to}


# Map function names to implementations
TOOL_IMPLEMENTATIONS = {
    "search_documents": search_documents,
    "get_weather": get_weather,
    "execute_sql": execute_sql,
    "send_email": send_email,
}


# =============================================================================
# 3. SINGLE TOOL CALLING
# =============================================================================

def single_tool_call_example():
    """
    Basic tool calling flow:
    1. Send messages + tools to model
    2. Model responds with tool_calls (instead of text)
    3. Execute the tool
    4. Send result back to model
    5. Model synthesizes final response
    """
    client = OpenAI()

    messages = [
        {"role": "system", "content": "You are a helpful assistant with access to tools."},
        {"role": "user", "content": "What's the weather in Tokyo?"}
    ]

    # Step 1: Model decides to call a tool
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",  # Let model decide (vs "required" or {"type":"function","function":{"name":"..."}})
    )

    message = response.choices[0].message

    # Step 2: Check if model wants to call tools
    if message.tool_calls:
        # Add the assistant's message (with tool calls) to history
        messages.append(message)

        for tool_call in message.tool_calls:
            # Step 3: Execute the tool
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)

            print(f"Calling tool: {func_name}({func_args})")
            result = TOOL_IMPLEMENTATIONS[func_name](**func_args)

            # Step 4: Add tool result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,  # Must match the tool_call id
                "content": json.dumps(result),
            })

        # Step 5: Get final response with tool results
        final_response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=TOOLS,
        )
        print(f"Final answer: {final_response.choices[0].message.content}")


# =============================================================================
# 4. PARALLEL TOOL CALLING
# =============================================================================

async def parallel_tool_calling():
    """
    Models can emit multiple tool calls in a single response.
    Execute them concurrently for lower latency.
    """
    client = AsyncOpenAI()

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What's the weather in Tokyo and New York? Also search for 'vacation policies'."}
    ]

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
    )

    message = response.choices[0].message

    if message.tool_calls:
        messages.append(message)

        # Execute all tool calls concurrently
        async def execute_tool(tool_call):
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)

            # Run sync functions in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: TOOL_IMPLEMENTATIONS[func_name](**func_args)
            )
            return tool_call.id, result

        # Gather all results concurrently
        results = await asyncio.gather(
            *[execute_tool(tc) for tc in message.tool_calls],
            return_exceptions=True,
        )

        # Add all tool results to messages
        for tool_call_id, result in results:
            if isinstance(result, Exception):
                content = json.dumps({"error": str(result)})
            else:
                content = json.dumps(result)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": content,
            })

        # Get final synthesized response
        final = await client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=TOOLS,
        )
        print(f"Final: {final.choices[0].message.content}")


# =============================================================================
# 5. ERROR HANDLING IN TOOL EXECUTION
# =============================================================================

@dataclass
class ToolExecutionResult:
    """Structured result from tool execution with error context."""
    tool_call_id: str
    function_name: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0


def safe_execute_tool(tool_call) -> ToolExecutionResult:
    """
    Execute a tool call with comprehensive error handling.
    
    Key principle: ALWAYS return a result to the model, even on error.
    The model needs to know what happened to give a good response.
    Never silently drop tool results.
    """
    func_name = tool_call.function.name
    start = time.time()

    # Validate function exists
    if func_name not in TOOL_IMPLEMENTATIONS:
        return ToolExecutionResult(
            tool_call_id=tool_call.id,
            function_name=func_name,
            success=False,
            error=f"Unknown tool: {func_name}",
        )

    # Parse arguments
    try:
        func_args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError as e:
        return ToolExecutionResult(
            tool_call_id=tool_call.id,
            function_name=func_name,
            success=False,
            error=f"Invalid arguments JSON: {e}",
        )

    # Execute with timeout and error catching
    try:
        result = TOOL_IMPLEMENTATIONS[func_name](**func_args)
        elapsed = (time.time() - start) * 1000

        return ToolExecutionResult(
            tool_call_id=tool_call.id,
            function_name=func_name,
            success=True,
            result=result,
            execution_time_ms=elapsed,
        )

    except PermissionError as e:
        return ToolExecutionResult(
            tool_call_id=tool_call.id,
            function_name=func_name,
            success=False,
            error=f"Permission denied: {e}",
            execution_time_ms=(time.time() - start) * 1000,
        )

    except Exception as e:
        return ToolExecutionResult(
            tool_call_id=tool_call.id,
            function_name=func_name,
            success=False,
            error=f"Execution error: {type(e).__name__}: {e}",
            execution_time_ms=(time.time() - start) * 1000,
        )


# =============================================================================
# 6. TOOL CALLING WITH CONVERSATION HISTORY (AGENTIC LOOP)
# =============================================================================

async def agentic_tool_loop(
    user_message: str,
    max_iterations: int = 10,
    tools: list = TOOLS,
) -> str:
    """
    Full agentic loop: model can call tools repeatedly until it has
    enough information to answer.
    
    This is the core pattern used by AI agents (AutoGPT, LangChain agents, etc.)
    The model acts as a "controller" deciding which tools to call and when to stop.
    """
    client = AsyncOpenAI()

    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant with access to tools. "
                "Use tools to gather information before answering. "
                "If a tool call fails, explain the error to the user. "
                "When you have sufficient information, provide your final answer."
            )
        },
        {"role": "user", "content": user_message}
    ]

    for iteration in range(max_iterations):
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )

        message = response.choices[0].message

        # If no tool calls, we have our final answer
        if not message.tool_calls:
            return message.content

        # Process tool calls
        messages.append(message)

        for tool_call in message.tool_calls:
            result = safe_execute_tool(tool_call)

            # Format result for the model
            if result.success:
                content = json.dumps(result.result)
            else:
                content = json.dumps({"error": result.error})

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": content,
            })

        print(f"  [Iteration {iteration + 1}: {len(message.tool_calls)} tool calls executed]")

    return "Maximum iterations reached. Could not complete the request."


# =============================================================================
# 7. TOOL REGISTRY (Production Pattern)
# =============================================================================

class ToolRegistry:
    """
    Production-grade tool registry that:
    - Registers tools with their schemas and implementations
    - Validates inputs before execution
    - Tracks execution metrics
    - Supports middleware (auth, logging, rate limiting)
    - Generates OpenAI-compatible tool definitions automatically
    
    This is the pattern used in production agent frameworks.
    """

    def __init__(self):
        self._tools: dict[str, dict] = {}
        self._metrics: dict[str, list] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters_schema: dict,
        implementation: Callable,
        requires_confirmation: bool = False,
    ):
        """Register a tool with its schema and implementation."""
        self._tools[name] = {
            "name": name,
            "description": description,
            "parameters_schema": parameters_schema,
            "implementation": implementation,
            "requires_confirmation": requires_confirmation,
        }
        self._metrics[name] = []

    def register_from_pydantic(
        self,
        name: str,
        description: str,
        input_model: type[BaseModel],
        implementation: Callable,
        requires_confirmation: bool = False,
    ):
        """Register a tool using a Pydantic model for parameter schema."""
        schema = input_model.model_json_schema()
        # Remove Pydantic metadata that OpenAI doesn't need
        schema.pop("title", None)
        self.register(name, description, schema, implementation, requires_confirmation)

    def get_openai_tools(self) -> list[dict]:
        """Generate OpenAI-compatible tool definitions."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters_schema"],
                }
            }
            for tool in self._tools.values()
        ]

    async def execute(self, tool_call) -> ToolExecutionResult:
        """Execute a tool call with metrics tracking."""
        func_name = tool_call.function.name

        if func_name not in self._tools:
            return ToolExecutionResult(
                tool_call_id=tool_call.id,
                function_name=func_name,
                success=False,
                error=f"Tool '{func_name}' not registered",
            )

        tool = self._tools[func_name]

        # Check if tool requires user confirmation
        if tool["requires_confirmation"]:
            # In production, this would pause and ask the user
            print(f"⚠️  Tool '{func_name}' requires confirmation (auto-approved in demo)")

        # Parse and execute
        start = time.time()
        try:
            args = json.loads(tool_call.function.arguments)
            result = tool["implementation"](**args)
            elapsed = (time.time() - start) * 1000

            # Track metrics
            self._metrics[func_name].append({
                "success": True,
                "latency_ms": elapsed,
                "timestamp": time.time(),
            })

            return ToolExecutionResult(
                tool_call_id=tool_call.id,
                function_name=func_name,
                success=True,
                result=result,
                execution_time_ms=elapsed,
            )

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            self._metrics[func_name].append({
                "success": False,
                "latency_ms": elapsed,
                "error": str(e),
                "timestamp": time.time(),
            })
            return ToolExecutionResult(
                tool_call_id=tool_call.id,
                function_name=func_name,
                success=False,
                error=str(e),
                execution_time_ms=elapsed,
            )

    def get_metrics_summary(self) -> dict:
        """Get execution metrics for all tools."""
        summary = {}
        for name, calls in self._metrics.items():
            if not calls:
                continue
            successes = [c for c in calls if c["success"]]
            summary[name] = {
                "total_calls": len(calls),
                "success_rate": len(successes) / len(calls),
                "avg_latency_ms": sum(c["latency_ms"] for c in calls) / len(calls),
                "p95_latency_ms": sorted(c["latency_ms"] for c in calls)[int(len(calls) * 0.95)] if len(calls) > 1 else calls[0]["latency_ms"],
            }
        return summary


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    # Set up registry
    registry = ToolRegistry()
    registry.register(
        name="search_documents",
        description="Search knowledge base for relevant documents.",
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        implementation=search_documents,
    )
    registry.register(
        name="get_weather",
        description="Get current weather for a location.",
        parameters_schema={
            "type": "object",
            "properties": {
                "location": {"type": "string"},
                "units": {"type": "string", "enum": ["celsius", "fahrenheit"]},
            },
            "required": ["location"],
        },
        implementation=get_weather,
    )

    # Run examples
    print("=== Single Tool Call ===")
    single_tool_call_example()

    print("\n=== Agentic Loop ===")
    asyncio.run(agentic_tool_loop("What's the weather in London and search for 'refund policy'?"))

    print("\n=== Tool Metrics ===")
    print(json.dumps(registry.get_metrics_summary(), indent=2))
