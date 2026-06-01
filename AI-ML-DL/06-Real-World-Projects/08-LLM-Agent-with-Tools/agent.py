"""
Project 8: LLM Agent with Tools (ReAct Pattern)
================================================

Demonstrates the ReAct (Reasoning + Acting) pattern for LLM agents.
Uses a rule-based "mini LLM" to show the agent loop without API keys.

Educational Purpose:
- Understand how LLM agents decide which tools to use
- See the Thought → Action → Observation loop in action
- Learn tool definition patterns (name, description, function)
- Observe how tool results feed back into reasoning

Run: python agent.py
"""

import logging
import re
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Tool Definitions
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Tool:
    """A tool that the agent can invoke."""
    name: str
    description: str
    func: Callable[[str], str]


def calculator(expression: str) -> str:
    """Safely evaluate a mathematical expression."""
    try:
        # Allow only safe math operations
        allowed = set("0123456789+-*/.() %")
        clean = expression.strip()
        if not all(c in allowed for c in clean):
            return f"Error: unsafe expression '{clean}'"
        result = eval(clean, {"__builtins__": {}}, {"math": math})
        return str(result)
    except Exception as e:
        return f"Error: {e}"


def search(query: str) -> str:
    """Mock search engine with pre-defined knowledge."""
    knowledge = {
        "population of france": "France has a population of approximately 68 million people (2024).",
        "population of india": "India has a population of approximately 1.44 billion people (2024).",
        "capital of japan": "The capital of Japan is Tokyo.",
        "speed of light": "The speed of light is approximately 299,792,458 meters per second.",
        "python creator": "Python was created by Guido van Rossum and first released in 1991.",
        "tallest mountain": "Mount Everest is the tallest mountain at 8,849 meters above sea level.",
        "distance earth to moon": "The average distance from Earth to the Moon is 384,400 km.",
        "boiling point of water": "Water boils at 100°C (212°F) at standard atmospheric pressure.",
    }
    query_lower = query.lower().strip()
    for key, value in knowledge.items():
        if key in query_lower or any(w in query_lower for w in key.split()):
            return value
    return f"No results found for: {query}"


def weather_lookup(location: str) -> str:
    """Mock weather service."""
    weather_data = {
        "paris": "Paris: 18°C, partly cloudy, humidity 65%",
        "tokyo": "Tokyo: 24°C, sunny, humidity 55%",
        "new york": "New York: 15°C, rainy, humidity 80%",
        "london": "London: 12°C, overcast, humidity 75%",
        "sydney": "Sydney: 22°C, clear skies, humidity 50%",
    }
    loc = location.lower().strip()
    for key, value in weather_data.items():
        if key in loc:
            return value
    return f"Weather data not available for: {location}"


def get_datetime(query: str) -> str:
    """Get current date and time information."""
    now = datetime.now()
    if "date" in query.lower():
        return f"Current date: {now.strftime('%Y-%m-%d')}"
    elif "time" in query.lower():
        return f"Current time: {now.strftime('%H:%M:%S')}"
    elif "day" in query.lower():
        return f"Today is {now.strftime('%A, %B %d, %Y')}"
    return f"Current datetime: {now.strftime('%Y-%m-%d %H:%M:%S')}"


# ─────────────────────────────────────────────────────────────────────────────
# Agent Reasoning Engine (Rule-Based "Mini LLM")
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AgentStep:
    """One step in the agent's reasoning trace."""
    step_num: int
    thought: str
    action: str
    action_input: str
    observation: str


class ReActAgent:
    """
    ReAct Agent implementing the Thought → Action → Observation loop.
    Uses rule-based reasoning to demonstrate the pattern without an LLM.
    """

    def __init__(self, tools: list[Tool], max_steps: int = 5):
        self.tools = {t.name: t for t in tools}
        self.max_steps = max_steps
        self.trace: list[AgentStep] = []

    def _select_tool_and_input(self, query: str, history: list[AgentStep]) -> tuple[str, str, str]:
        """
        Rule-based tool selection (simulates what an LLM would do).
        Returns (thought, tool_name, tool_input).
        """
        query_lower = query.lower()

        # If we already have observations, check if we can finish
        if history:
            last_obs = history[-1].observation
            # Check if a calculation was needed after a search
            if any(w in query_lower for w in ["percent", "%", "how many", "calculate"]):
                # Look for numbers in observations
                numbers = re.findall(r"[\d,]+\.?\d*", last_obs.replace(",", ""))
                if numbers and not any(h.action == "calculator" for h in history):
                    # Extract percentage if present in query
                    pct_match = re.search(r"(\d+)%|(\d+)\s*percent", query_lower)
                    if pct_match:
                        pct = pct_match.group(1) or pct_match.group(2)
                        num = numbers[-1]
                        expr = f"{num} * {pct} / 100"
                        return (
                            f"I found that the number is {num}. Now I need to calculate {pct}% of it.",
                            "calculator",
                            expr,
                        )

            # We have enough info to answer
            return (
                "I have enough information to answer the question.",
                "finish",
                self._synthesize_answer(query, history),
            )

        # First step: determine which tool to use
        if any(w in query_lower for w in ["weather", "temperature", "forecast"]):
            location = self._extract_location(query)
            return (
                f"The user wants weather information. I'll look up the weather for {location}.",
                "weather_lookup",
                location,
            )
        elif any(w in query_lower for w in ["date", "time", "today", "day"]):
            return (
                "The user wants date/time information.",
                "get_datetime",
                query,
            )
        elif re.search(r"\d", query) and not any(
            w in query_lower for w in ["population", "capital", "who", "what is the"]
        ):
            # Pure math expression - convert "X% of Y" to "Y * X / 100"
            pct_of = re.search(r"(\d+)%?\s*(?:of|percent of)\s*(\d[\d,.]*)", query_lower)
            if pct_of:
                math_expr = f"{pct_of.group(2).replace(',','')} * {pct_of.group(1)} / 100"
            else:
                # Extract numbers and operators
                nums = re.findall(r"[\d.]+", query)
                ops = re.findall(r"[+\-*/]", query)
                if nums and ops:
                    math_expr = f"{nums[0]} {ops[0]} {nums[1]}" if len(nums) > 1 else query
                elif nums:
                    math_expr = " * ".join(nums) if len(nums) > 1 else nums[0]
                else:
                    math_expr = query
            return (
                f"This is a math problem. I'll calculate: {math_expr}",
                "calculator",
                math_expr,
            )
        elif any(w in query_lower for w in [
            "population", "capital", "who", "speed", "creator",
            "tallest", "distance", "boiling",
        ]):
            return (
                "I need to look up factual information to answer this question.",
                "search",
                query,
            )
        else:
            # Default: try search
            return (
                "Let me search for information about this topic.",
                "search",
                query,
            )

    def _extract_location(self, query: str) -> str:
        """Extract a location from a weather query."""
        # Remove common weather words
        cleaned = re.sub(
            r"\b(what|is|the|weather|like|in|temperature|forecast|for|today|how|hot|cold)\b",
            "", query, flags=re.IGNORECASE,
        ).strip()
        return cleaned if cleaned else "unknown"

    def _synthesize_answer(self, query: str, history: list[AgentStep]) -> str:
        """Synthesize a final answer from all observations."""
        observations = [h.observation for h in history]
        if len(observations) == 1:
            return observations[0]
        # Combine observations into a coherent answer
        return " Based on my research: " + " ".join(observations)

    def run(self, query: str) -> str:
        """Execute the ReAct loop for a given query."""
        self.trace = []
        separator = "─" * 60

        print(f'\nQUERY: "{query}"')
        print(separator)

        for step_num in range(1, self.max_steps + 1):
            thought, action, action_input = self._select_tool_and_input(query, self.trace)

            print(f"\nStep {step_num}:")
            print(f"  Thought: {thought}")
            print(f'  Action: {action}("{action_input}")')

            # Handle finish action
            if action == "finish":
                print(f"\nFINAL ANSWER: {action_input}")
                print(separator)
                return action_input

            # Execute tool
            if action in self.tools:
                observation = self.tools[action].func(action_input)
            else:
                observation = f"Error: Unknown tool '{action}'"

            print(f"  Observation: {observation}")

            self.trace.append(AgentStep(
                step_num=step_num,
                thought=thought,
                action=action,
                action_input=action_input,
                observation=observation,
            ))

        # Max steps reached
        final = self._synthesize_answer(query, self.trace)
        print(f"\nFINAL ANSWER (max steps): {final}")
        print(separator)
        return final


# ─────────────────────────────────────────────────────────────────────────────
# Main Demo
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Run the agent demo with various queries."""
    print("=" * 60)
    print("       LLM AGENT WITH TOOLS - ReAct Pattern")
    print("=" * 60)

    # Register tools
    tools = [
        Tool(
            name="calculator",
            description="Evaluates mathematical expressions. Input: a math expression string.",
            func=calculator,
        ),
        Tool(
            name="search",
            description="Searches for factual information. Input: a search query.",
            func=search,
        ),
        Tool(
            name="weather_lookup",
            description="Gets current weather for a location. Input: city name.",
            func=weather_lookup,
        ),
        Tool(
            name="get_datetime",
            description="Gets current date/time. Input: 'date', 'time', or 'day'.",
            func=get_datetime,
        ),
    ]

    print("\nRegistered Tools:")
    for t in tools:
        print(f"  • {t.name}: {t.description}")

    agent = ReActAgent(tools=tools, max_steps=5)

    # Example queries demonstrating different tool usage patterns
    queries = [
        "What is 15% of 380?",
        "What's the weather like in Tokyo?",
        "What day is it today?",
        "Who created Python?",
        "What is the capital of Japan?",
        "What is 25% of the population of France?",
        "What is the speed of light?",
    ]

    for q in queries:
        agent.run(q)

    print("\n" + "=" * 60)
    print("Demo complete! In production, replace the rule-based reasoning")
    print("with an LLM API (OpenAI function calling, Anthropic tool use).")
    print("=" * 60)


if __name__ == "__main__":
    main()
