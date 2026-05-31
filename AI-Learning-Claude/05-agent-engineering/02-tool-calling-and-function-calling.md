# Tool Calling and Function Calling

## The "Hands" of an AI Agent

An LLM without tools is like a brilliant mind trapped in a jar — it can think and reason but can't **do** anything in the real world. Tool calling gives the LLM **hands**:

- **Search** — hands that can reach into the internet
- **Calculator** — hands that can do precise math
- **Database** — hands that can look up records
- **API** — hands that can trigger actions in other systems

Without tools, an LLM can only generate text. With tools, it can **take action**.

---

## How Function Calling Works (OpenAI API)

The flow has 3 players: **your code**, **the LLM**, and **your tools**.

```mermaid
sequenceDiagram
    participant App as Your Application
    participant LLM as OpenAI LLM
    participant Tool as Tool Functions

    App->>LLM: User message + tool definitions
    LLM-->>App: "I want to call get_weather(city='Tokyo')"
    App->>Tool: Execute get_weather("Tokyo")
    Tool-->>App: {"temp": 22, "condition": "sunny"}
    App->>LLM: Here's the tool result: {...}
    LLM-->>App: "The weather in Tokyo is 22°C and sunny!"
    App->>App: Return to user
```

**Critical insight**: The LLM **never executes tools itself**. It only **decides** which tool to call and with what arguments. YOUR code executes the tool and feeds the result back.

---

## Tool Definition Schema

Every tool is defined with three things:

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",                    # What to call it
            "description": "Get current weather for a city. "
                          "Use when user asks about weather, "
                          "temperature, or conditions.",       # When to use it
            "parameters": {                            # What arguments it needs
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name, e.g., 'San Francisco'"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "Temperature unit"
                    }
                },
                "required": ["city"]
            }
        }
    }
]
```

The LLM reads descriptions to decide which tool to use — **the tool is only as good as its description**.

---

## The LLM's Role in Tool Calling

The LLM does two things:

1. **Decides WHICH tool** — Based on the user's intent and tool descriptions
2. **Decides WHAT arguments** — Extracts or infers parameter values from context

The LLM does NOT:
- Execute the tool
- Have access to the tool's implementation
- Know the tool's response until you feed it back

Think of the LLM as a **dispatcher** — it reads the request and routes it to the right department with the right info.

---

## Single vs Parallel Tool Calls

### Single Tool Call
```
User: "What's the weather in Tokyo?"
LLM: → calls get_weather(city="Tokyo")
```

### Parallel Tool Calls
```
User: "Compare weather in Tokyo and Paris"
LLM: → calls get_weather(city="Tokyo") AND get_weather(city="Paris")
     (both in the same response)
```

Parallel tool calls are more efficient — one round trip instead of two. The LLM can request multiple tool calls simultaneously when they're independent.

---

## Tool Execution Flow (Detailed)

```mermaid
flowchart TD
    A[User Message] --> B[Send to LLM with tool definitions]
    B --> C{LLM Response Type?}
    C -->|Text| D[Return text to user]
    C -->|Tool Call| E[Extract tool name + args]
    E --> F[Validate arguments]
    F --> G{Valid?}
    G -->|No| H[Return error to LLM]
    G -->|Yes| I[Execute tool function]
    I --> J{Success?}
    J -->|Yes| K[Send result to LLM]
    J -->|No| L[Send error to LLM]
    K --> B
    L --> B
    H --> B

    style D fill:#c8e6c9
```

This loop continues until the LLM responds with text (no more tool calls needed).

---

## Designing Good Tool Descriptions

The description is the LLM's **only guide** for when and how to use a tool. Bad descriptions = bad tool usage.

| Bad Description | Good Description |
|----------------|-----------------|
| "Search" | "Search the product catalog by name, category, or price range. Returns top 10 matching products with name, price, and availability." |
| "Send email" | "Send an email to a customer. Use ONLY for order confirmations and shipping updates. Never for marketing." |
| "Calculate" | "Perform arithmetic calculations. Input a math expression like '2 + 2' or '15% of 230'. Use for precise numbers, never estimate." |

### Rules for Great Tool Descriptions:
1. **State when to use it** — "Use when the user asks about..."
2. **State when NOT to use it** — "Do NOT use for..."
3. **Describe what it returns** — "Returns a list of..."
4. **Include examples** — "e.g., 'San Francisco, CA'"
5. **Mention limitations** — "Only works for US addresses"

---

## Tool Error Handling

Tools fail. Networks time out. APIs return errors. Your agent must handle this gracefully.

```python
def execute_tool(tool_name, arguments):
    try:
        result = tool_functions[tool_name](**arguments)
        return {"status": "success", "data": result}
    except ToolNotFoundError:
        return {"status": "error", "message": f"Tool '{tool_name}' does not exist"}
    except ValidationError as e:
        return {"status": "error", "message": f"Invalid arguments: {e}"}
    except TimeoutError:
        return {"status": "error", "message": "Tool timed out, try again"}
    except Exception as e:
        return {"status": "error", "message": f"Tool failed: {str(e)}"}
```

When you send an error back to the LLM, it can:
- Try a different tool
- Try different arguments
- Ask the user for clarification
- Give up gracefully

---

## Tool Safety: The Danger Zone

Not all tools are equal in risk:

| Safety Level | Tools | Supervision |
|-------------|-------|-------------|
| **Safe (read-only)** | search, get_weather, lookup | None needed |
| **Moderate (writes)** | send_email, create_ticket | Log + audit |
| **Dangerous (money/data)** | transfer_money, delete_records | Human approval |
| **Forbidden** | execute_arbitrary_code, sudo | Never unsupervised |

**Principle of Least Privilege**: Give the agent only the tools it needs for its specific task. A customer support agent doesn't need `delete_database`.

---

## The Tool Contract Pattern

Every production tool should have a clear contract:

```python
class ToolContract:
    name: str                    # Unique identifier
    description: str             # When and how to use
    input_schema: dict           # JSON Schema for parameters
    output_schema: dict          # What the response looks like
    side_effects: list[str]      # What it changes in the world
    permissions_required: list   # What access it needs
    rate_limit: str              # How often it can be called
    idempotent: bool            # Safe to retry?
    timeout_ms: int             # How long before giving up
```

This contract helps architects:
- **Audit** what agents can do
- **Test** tools in isolation
- **Monitor** tool usage patterns
- **Restrict** tools per agent role

---

## Key Takeaways

- Tool calling = LLM decides, your code executes
- The LLM never sees tool code; it only reads descriptions
- Good descriptions are the #1 factor in tool calling accuracy
- Always handle errors and feed them back to the LLM
- Apply least-privilege: only give tools the agent actually needs
- Parallel tool calls improve efficiency for independent operations
- Every production tool needs a contract: schema + side effects + permissions

---

## Staff-Level: Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|-------------|-------------|-----|
| Too many tools (>20) | Model gets confused, selection accuracy drops sharply | Group into categories, use a "tool selector" layer, or give role-specific subsets |
| Tools without error handling | Agent gets raw exceptions, hallucinates recovery | Wrap every tool in try/catch, return structured error objects |
| No tool execution timeout | Single hung API call blocks the entire agent indefinitely | Set timeouts (5-30s typical), kill and return timeout error to LLM |
| Ambiguous tool descriptions | Model picks wrong tool or invents wrong arguments | Be extremely specific: state WHEN to use, WHEN NOT to, WHAT it returns, with EXAMPLES |
| Tools that return too much data | Floods context window, agent can't find relevant info | Paginate, summarize, or return only top-K results with a "more available" flag |
| No idempotency on write tools | Retries cause double-sends, double-charges | Make write tools idempotent or add deduplication keys |

---

## Staff-Level: Trade-offs

### Many Specific Tools vs Few General Tools

| Many Specific (30+ tools) | Few General (5-8 tools) |
|--------------------------|------------------------|
| Higher precision per tool | Model selects more accurately |
| Easier to audit/permission individually | Simpler to maintain and test |
| Selection accuracy degrades | May need complex argument parsing |
| Better for narrow domains | Better for broad assistants |

**The sweet spot**: 8-15 well-described tools for most production agents.

### Parallel vs Sequential Execution

| Parallel | Sequential |
|---------|-----------|
| Faster (wall-clock time) | Simpler error handling |
| Independent operations only | Can use results of previous calls |
| Harder to debug ordering issues | Predictable execution trace |
| Better for data gathering | Better for stateful workflows |

---

## Staff-Level: Real Numbers

**Tool selection accuracy by tool count** (empirical observations across GPT-4, Claude, Gemini):

```
Tools    Accuracy    Notes
1-5      ~98%        Almost never picks wrong tool
6-10     ~95%        Occasional confusion with similar tools
11-15    ~90%        Needs excellent descriptions to maintain
16-20    ~82%        Noticeable degradation begins
21-30    ~70%        Frequent mis-selection, needs mitigation
30+      ~55%        Effectively random for similar tools
```

**Mitigation strategies when you MUST have many tools**:
1. **Two-stage selection**: First LLM call picks category, second call picks specific tool from subset
2. **Dynamic tool loading**: Only expose tools relevant to current task phase
3. **Tool descriptions as the primary lever**: Spending 30 min on descriptions > spending days on framework code
4. **Few-shot examples in system prompt**: Show the model correct tool selection for ambiguous cases

**Production benchmarks**:
- Tool execution p50 latency target: <2s
- Tool execution p99 latency target: <10s
- Timeout: 30s hard kill
- Budget: max 10 tool calls per agent turn (configurable per use case)

---

## Tool Reliability Monitoring

Track per tool:
- **Success rate**: target >99% (alert at <97%)
- **Latency percentiles**: p50, p95, p99 — detect degradation before users notice
- **Error classification**: transient (retry-worthy) vs. permanent (don't retry)
- **Invocation frequency**: detect if model stops using a tool (possible description regression)
- **Cost per call**: especially for paid APIs — set per-tool budget caps

## Tool Deprecation Strategies

When retiring a tool:
1. **Shadow period**: Keep old tool available but log warnings when invoked
2. **Redirect**: Map old tool name to new tool internally (backward compat for cached prompts)
3. **Graceful removal**: Remove from tool list, but if model hallucinates old tool name, return helpful error ("this tool was replaced by X")
4. **Version in tool names** for breaking changes: `search_v2` alongside `search_v1` during transition
