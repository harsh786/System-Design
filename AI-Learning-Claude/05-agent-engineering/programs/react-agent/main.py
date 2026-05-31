"""
ReAct Agent from Scratch
========================
Implements the ReAct (Reasoning + Acting) pattern without any framework.
The agent thinks out loud, chooses tools, observes results, and iterates.
"""

import os
import json
import math
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =============================================================================
# TOOLS - The agent's "hands"
# =============================================================================

def web_search(query: str) -> str:
    """Simulated web search - returns pre-defined results for demo purposes."""
    search_db = {
        "eiffel tower height": "The Eiffel Tower is 330 meters (1,083 feet) tall, located in Paris, France. Built in 1889.",
        "france population 2024": "France population in 2024 is approximately 68.4 million people.",
        "python creator": "Python was created by Guido van Rossum, first released in 1991.",
        "largest ocean": "The Pacific Ocean is the largest ocean, covering about 165.25 million square kilometers.",
        "speed of light": "The speed of light in vacuum is 299,792,458 meters per second (approximately 3 × 10^8 m/s).",
        "mars distance from sun": "Mars is approximately 228 million kilometers (142 million miles) from the Sun on average.",
        "openai founded": "OpenAI was founded in December 2015 by Sam Altman, Greg Brockman, Elon Musk, and others.",
    }
    query_lower = query.lower()
    for key, value in search_db.items():
        if key in query_lower or any(word in query_lower for word in key.split()):
            return value
    return f"No results found for '{query}'. Try a different search query."


def calculator(expression: str) -> str:
    """Evaluates a mathematical expression safely."""
    try:
        # Allow only safe math operations
        allowed_names = {
            "abs": abs, "round": round, "min": min, "max": max,
            "pow": pow, "sqrt": math.sqrt, "pi": math.pi, "e": math.e,
        }
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return f"{expression} = {result}"
    except Exception as e:
        return f"Error calculating '{expression}': {str(e)}"


def knowledge_base(topic: str) -> str:
    """Looks up facts from a simulated knowledge base."""
    kb = {
        "eiffel tower": "The Eiffel Tower is a wrought-iron lattice tower in Paris, France. Height: 330m. Built: 1889. Architect: Gustave Eiffel.",
        "photosynthesis": "Photosynthesis converts CO2 + H2O + light energy into glucose + oxygen. Occurs in chloroplasts.",
        "python": "Python is a high-level programming language. Created by Guido van Rossum (1991). Known for readability.",
        "machine learning": "ML is a subset of AI where systems learn from data. Types: supervised, unsupervised, reinforcement learning.",
        "solar system": "Our solar system has 8 planets: Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, Neptune. Sun is a G-type star.",
    }
    topic_lower = topic.lower()
    for key, value in kb.items():
        if key in topic_lower or topic_lower in key:
            return value
    return f"No entry found for '{topic}' in knowledge base."


# Tool registry
TOOLS = {
    "web_search": {"fn": web_search, "desc": "Search the web for current information"},
    "calculator": {"fn": calculator, "desc": "Evaluate mathematical expressions"},
    "knowledge_base": {"fn": knowledge_base, "desc": "Look up factual information"},
}

# =============================================================================
# REACT AGENT
# =============================================================================

REACT_SYSTEM_PROMPT = """You are a ReAct agent. You solve tasks by thinking step-by-step and using tools.

For EACH step, you MUST output exactly this format:

Thought: [Your reasoning about what to do next]
Action: [tool_name("argument")]

When you have enough information to answer, output:
Thought: [Your final reasoning]
Action: final_answer("your complete answer")

Available tools:
- web_search("query"): Search the web for current information
- calculator("math expression"): Compute math (e.g., "330 * 3.281")
- knowledge_base("topic"): Look up factual information

RULES:
- Always think before acting
- Use tools to verify facts, never guess
- If a tool returns no results, try a different query
- You MUST use the exact format above
"""


def parse_react_response(response: str) -> tuple[str, str, str]:
    """Parse the LLM response into thought, tool_name, and tool_arg."""
    thought = ""
    tool_name = ""
    tool_arg = ""

    lines = response.strip().split("\n")
    for line in lines:
        if line.startswith("Thought:"):
            thought = line[len("Thought:"):].strip()
        elif line.startswith("Action:"):
            action_str = line[len("Action:"):].strip()
            # Parse: tool_name("argument")
            if "(" in action_str and action_str.endswith(")"):
                tool_name = action_str[:action_str.index("(")]
                tool_arg = action_str[action_str.index("(") + 1:-1].strip().strip('"\'')

    return thought, tool_name, tool_arg


def run_react_agent(task: str, max_iterations: int = 8) -> str:
    """Run the ReAct agent loop."""
    print("=" * 60)
    print(f"🎯 TASK: {task}")
    print("=" * 60)

    messages = [
        {"role": "system", "content": REACT_SYSTEM_PROMPT},
        {"role": "user", "content": f"Task: {task}"},
    ]

    previous_actions = []

    for i in range(max_iterations):
        print(f"\n{'─' * 40}")
        print(f"  STEP {i + 1}")
        print(f"{'─' * 40}")

        # Get LLM response
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0,
            max_tokens=300,
        )
        reply = response.choices[0].message.content
        thought, tool_name, tool_arg = parse_react_response(reply)

        print(f"  💭 Thought: {thought}")
        print(f"  🔧 Action:  {tool_name}(\"{tool_arg}\")")

        # Check for final answer
        if tool_name == "final_answer":
            print(f"\n{'=' * 60}")
            print(f"✅ FINAL ANSWER: {tool_arg}")
            print(f"{'=' * 60}")
            print(f"\n📊 Completed in {i + 1} steps")
            return tool_arg

        # Loop detection
        current_action = f"{tool_name}({tool_arg})"
        if previous_actions.count(current_action) >= 2:
            print("  ⚠️  Loop detected! Same action repeated 3 times.")
            messages.append({"role": "assistant", "content": reply})
            messages.append({
                "role": "user",
                "content": "Observation: You've tried this exact action before with no new results. Try a completely different approach or provide your best answer with final_answer()."
            })
            previous_actions.append(current_action)
            continue
        previous_actions.append(current_action)

        # Execute tool
        if tool_name in TOOLS:
            observation = TOOLS[tool_name]["fn"](tool_arg)
        else:
            observation = f"Error: Tool '{tool_name}' does not exist. Available: {list(TOOLS.keys())}"

        print(f"  👁️  Observation: {observation}")

        # Add to message history
        messages.append({"role": "assistant", "content": reply})
        messages.append({"role": "user", "content": f"Observation: {observation}"})

    print(f"\n⚠️  Max iterations ({max_iterations}) reached without final answer.")
    return "Could not complete task within iteration limit."


# =============================================================================
# MAIN - Run example tasks
# =============================================================================

if __name__ == "__main__":
    tasks = [
        "What is the height of the Eiffel Tower in feet? Convert it from meters.",
        "Who created Python and in what year? What's interesting about the language?",
        "How long would it take light to travel from the Sun to Mars?",
    ]

    for task in tasks:
        run_react_agent(task)
        print("\n" + "🔄" * 30 + "\n")
