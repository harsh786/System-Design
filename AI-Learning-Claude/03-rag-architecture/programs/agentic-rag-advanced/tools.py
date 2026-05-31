"""
tools.py - Tool definitions for the Agentic RAG agent

Each tool:
1. Has a clear interface (name, description, parameters)
2. Returns structured results with source attribution
3. Can be selected by the agent based on query classification
"""

from knowledge_base import search_documents, query_structured, lookup_graph


# =============================================================================
# TOOL REGISTRY - Agent uses this to understand available tools
# =============================================================================

TOOL_REGISTRY = {
    "vector_search": {
        "description": "Semantic search over unstructured company documents. Best for: factual questions, policies, descriptions, general info.",
        "parameters": {"query": "str", "top_k": "int (default 3)"},
    },
    "sql_query": {
        "description": "Query structured data tables (employees, quarterly_financials, products, sales_targets). Best for: numbers, dates, specific records.",
        "parameters": {"table": "str", "filters": "dict (optional)"},
    },
    "graph_lookup": {
        "description": "Traverse entity relationships (who manages whom, team→products, product→team). Best for: organizational questions, ownership, hierarchy.",
        "parameters": {"entity": "str", "relationship": "str (optional)"},
    },
    "calculator": {
        "description": "Perform mathematical calculations. Best for: growth rates, averages, comparisons requiring math.",
        "parameters": {"expression": "str"},
    },
}


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================

def vector_search(query: str, top_k: int = 3) -> dict:
    """
    Semantic search over NovaTech documents.
    Returns results with relevance scores and source attribution.
    """
    results = search_documents(query, top_k)
    return {
        "tool": "vector_search",
        "query": query,
        "results": results,
        "source": "document_store",
        "result_count": len(results),
    }


def sql_query(table: str, filters: dict = None) -> dict:
    """
    Query structured data (simulated SQL).
    Supports tables: employees, quarterly_financials, products, sales_targets
    """
    results = query_structured(table, filters)
    return {
        "tool": "sql_query",
        "table": table,
        "filters": filters,
        "results": results,
        "source": f"structured_data.{table}",
        "result_count": len(results),
    }


def graph_lookup(entity: str, relationship: str = None) -> dict:
    """
    Traverse the entity relationship graph.
    Find connections: managed_by, products, members, reports_to, etc.
    """
    results = lookup_graph(entity, relationship)
    return {
        "tool": "graph_lookup",
        "entity": entity,
        "relationship": relationship,
        "results": results,
        "source": "entity_graph",
        "result_count": len(results),
    }


def calculator(expression: str) -> dict:
    """
    Evaluate a mathematical expression safely.
    Supports: +, -, *, /, **, (), round()
    """
    # Safe evaluation with limited builtins
    allowed = {"__builtins__": {}, "round": round, "abs": abs, "min": min, "max": max}
    try:
        result = eval(expression, allowed)
        return {
            "tool": "calculator",
            "expression": expression,
            "result": result,
            "source": "calculation",
            "result_count": 1,
        }
    except Exception as e:
        return {
            "tool": "calculator",
            "expression": expression,
            "result": None,
            "error": str(e),
            "source": "calculation",
            "result_count": 0,
        }


# =============================================================================
# TOOL DISPATCHER - Routes tool calls from the agent
# =============================================================================

def execute_tool(tool_name: str, **kwargs) -> dict:
    """Dispatch a tool call by name."""
    dispatch = {
        "vector_search": vector_search,
        "sql_query": sql_query,
        "graph_lookup": graph_lookup,
        "calculator": calculator,
    }
    if tool_name not in dispatch:
        return {"error": f"Unknown tool: {tool_name}", "result_count": 0}
    return dispatch[tool_name](**kwargs)
