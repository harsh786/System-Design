"""
Agent tools.
Tools available to the agent pipeline: vector_search, calculator, sql_query, get_current_info.
"""

from knowledge_base import knowledge_base


def vector_search(query: str, n_results: int = 3) -> dict:
    """Search the knowledge base for relevant information."""
    print(f"[TOOL:vector_search] Searching: '{query}'")
    results = knowledge_base.search(query, n_results=n_results)
    return {
        "tool": "vector_search",
        "query": query,
        "results": [{"text": r["text"], "score": r["score"], "id": r["id"]} for r in results],
        "count": len(results),
    }


def calculator(expression: str) -> dict:
    """Perform a math calculation. Supports basic arithmetic."""
    print(f"[TOOL:calculator] Calculating: '{expression}'")
    try:
        # Safe eval for basic math only
        allowed_chars = set("0123456789.+-*/() %")
        if not all(c in allowed_chars for c in expression.replace(" ", "")):
            return {"tool": "calculator", "error": "Invalid expression", "expression": expression}

        result = eval(expression)  # Safe due to character whitelist
        return {"tool": "calculator", "expression": expression, "result": result}
    except Exception as e:
        return {"tool": "calculator", "error": str(e), "expression": expression}


def sql_query(query_description: str) -> dict:
    """
    Simulated structured data query.
    In production, this would query a real database.
    """
    print(f"[TOOL:sql_query] Query: '{query_description}'")

    # Simulated results based on common queries
    simulated_data = {
        "revenue": {"q1": 3.1, "q2": 3.6, "q3": 4.2, "unit": "million USD"},
        "customers": {"q1": 180, "q2": 195, "q3": 220},
        "employees": {"total": 450, "engineering": 180, "sales": 80, "other": 190},
        "products": ["NovaAssist", "NovaAnalytics", "NovaGuard"],
    }

    # Match query to simulated data
    query_lower = query_description.lower()
    if "revenue" in query_lower:
        return {"tool": "sql_query", "query": query_description, "data": simulated_data["revenue"]}
    elif "customer" in query_lower:
        return {"tool": "sql_query", "query": query_description, "data": simulated_data["customers"]}
    elif "employee" in query_lower:
        return {"tool": "sql_query", "query": query_description, "data": simulated_data["employees"]}
    else:
        return {"tool": "sql_query", "query": query_description, "data": None, "note": "No matching data"}


def get_current_info(topic: str) -> dict:
    """
    Simulated API call for current information.
    In production, this would call external APIs.
    """
    print(f"[TOOL:get_current_info] Topic: '{topic}'")

    simulated_info = {
        "stock_price": {"value": "N/A", "note": "Stock data not available in demo"},
        "weather": {"value": "72°F, Sunny", "location": "Austin, TX"},
        "time": {"value": "2024-10-15T14:30:00Z", "timezone": "UTC"},
        "market": {"value": "Market data not available in demo"},
    }

    topic_lower = topic.lower()
    for key, info in simulated_info.items():
        if key in topic_lower:
            return {"tool": "get_current_info", "topic": topic, "data": info}

    return {"tool": "get_current_info", "topic": topic, "data": {"note": "Information not available"}}


# Tool registry
AVAILABLE_TOOLS = {
    "vector_search": {
        "function": vector_search,
        "description": "Search the knowledge base for relevant documents",
        "parameters": ["query"],
    },
    "calculator": {
        "function": calculator,
        "description": "Perform mathematical calculations",
        "parameters": ["expression"],
    },
    "sql_query": {
        "function": sql_query,
        "description": "Query structured data (revenue, customers, employees)",
        "parameters": ["query_description"],
    },
    "get_current_info": {
        "function": get_current_info,
        "description": "Get current real-time information",
        "parameters": ["topic"],
    },
}


def execute_tool(tool_name: str, **kwargs) -> dict:
    """Execute a tool by name with given arguments."""
    if tool_name not in AVAILABLE_TOOLS:
        return {"error": f"Unknown tool: {tool_name}"}

    tool = AVAILABLE_TOOLS[tool_name]
    try:
        result = tool["function"](**kwargs)
        return result
    except Exception as e:
        return {"error": f"Tool execution failed: {e}", "tool": tool_name}
