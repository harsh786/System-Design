"""
IMPLEMENTATION: Basic ReAct Agent with Full Lifecycle
=====================================================
A production-grade basic agent implementation demonstrating:
- ReAct loop (Reason-Act-Observe)
- Tool registry and execution
- State management with working memory
- Max steps, timeout, and token budget enforcement
- Guardrail hooks (pre/post action)
- Structured output parsing
- Error recovery and retry
- Episode history
"""

from __future__ import annotations

import json
import time
import uuid
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Protocol

# ============================================================
# DOMAIN TYPES
# ============================================================

class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_FOR_HUMAN = "waiting_for_human"
    COMPLETED = "completed"
    FAILED = "failed"
    MAX_STEPS_EXCEEDED = "max_steps_exceeded"
    TIMEOUT = "timeout"
    BUDGET_EXCEEDED = "budget_exceeded"


class ActionType(Enum):
    TOOL_CALL = "tool_call"
    RESPOND = "respond"
    ESCALATE = "escalate"
    WAIT = "wait"


@dataclass
class ToolParameter:
    name: str
    type: str
    description: str
    required: bool = True
    enum: list[str] | None = None
    default: Any = None


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: list[ToolParameter]
    handler: Callable[..., Any]
    requires_approval: bool = False
    max_retries: int = 2
    timeout_seconds: float = 30.0

    def to_schema(self) -> dict[str, Any]:
        """Convert to OpenAI-compatible function schema."""
        properties = {}
        required = []
        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                properties[param.name]["enum"] = param.enum
            if param.required:
                required.append(param.name)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


@dataclass
class AgentAction:
    type: ActionType
    tool_name: str | None = None
    tool_args: dict[str, Any] = field(default_factory=dict)
    response_text: str | None = None
    reasoning: str = ""


@dataclass
class Observation:
    content: str
    source: str  # "tool", "user", "system", "error"
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentStep:
    step_number: int
    reasoning: str
    action: AgentAction
    observation: Observation | None = None
    duration_ms: float = 0.0
    tokens_used: int = 0
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentEpisode:
    episode_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    goal: str = ""
    steps: list[AgentStep] = field(default_factory=list)
    status: AgentStatus = AgentStatus.IDLE
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_duration_ms: float = 0.0
    final_output: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenBudget:
    max_input_tokens: int = 100_000
    max_output_tokens: int = 10_000
    max_total_tokens: int = 150_000
    used_input_tokens: int = 0
    used_output_tokens: int = 0

    @property
    def used_total(self) -> int:
        return self.used_input_tokens + self.used_output_tokens

    @property
    def remaining(self) -> int:
        return self.max_total_tokens - self.used_total

    def is_exceeded(self) -> bool:
        return self.used_total >= self.max_total_tokens

    def record_usage(self, input_tokens: int, output_tokens: int) -> None:
        self.used_input_tokens += input_tokens
        self.used_output_tokens += output_tokens


# ============================================================
# GUARDRAILS
# ============================================================

class GuardrailResult:
    def __init__(self, allowed: bool, reason: str = ""):
        self.allowed = allowed
        self.reason = reason


class Guardrail(ABC):
    @abstractmethod
    def check(self, action: AgentAction, state: "AgentState") -> GuardrailResult:
        ...


class PreActionGuardrail(Guardrail):
    """Runs before tool execution. Can block actions."""
    pass


class PostActionGuardrail(Guardrail):
    """Runs after tool execution. Can flag/log issues."""
    pass


class BlockedToolsGuardrail(PreActionGuardrail):
    """Prevents calling specific tools in certain contexts."""

    def __init__(self, blocked_tools: list[str]):
        self.blocked_tools = blocked_tools

    def check(self, action: AgentAction, state: "AgentState") -> GuardrailResult:
        if action.tool_name in self.blocked_tools:
            return GuardrailResult(False, f"Tool '{action.tool_name}' is blocked by policy")
        return GuardrailResult(True)


class CostLimitGuardrail(PreActionGuardrail):
    """Prevents actions when cost threshold is exceeded."""

    def __init__(self, max_cost_usd: float):
        self.max_cost_usd = max_cost_usd

    def check(self, action: AgentAction, state: "AgentState") -> GuardrailResult:
        if state.episode.total_cost_usd >= self.max_cost_usd:
            return GuardrailResult(False, f"Cost limit ${self.max_cost_usd} exceeded")
        return GuardrailResult(True)


class SensitiveDataGuardrail(PostActionGuardrail):
    """Flags if tool output contains sensitive patterns."""

    def __init__(self, patterns: list[str]):
        self.patterns = patterns

    def check(self, action: AgentAction, state: "AgentState") -> GuardrailResult:
        # In production, check the observation content against patterns
        return GuardrailResult(True)


# ============================================================
# MEMORY
# ============================================================

@dataclass
class WorkingMemory:
    """Short-term memory for the current episode."""
    facts: list[str] = field(default_factory=list)
    user_preferences: dict[str, Any] = field(default_factory=dict)
    scratch_pad: str = ""

    def add_fact(self, fact: str) -> None:
        if fact not in self.facts:
            self.facts.append(fact)

    def to_context_string(self) -> str:
        parts = []
        if self.facts:
            parts.append("Known facts:\n" + "\n".join(f"- {f}" for f in self.facts))
        if self.user_preferences:
            parts.append("User preferences:\n" + json.dumps(self.user_preferences, indent=2))
        if self.scratch_pad:
            parts.append(f"Scratch pad:\n{self.scratch_pad}")
        return "\n\n".join(parts)


class EpisodeHistory:
    """Long-term memory of past episodes (for few-shot / learning)."""

    def __init__(self, max_episodes: int = 100):
        self.episodes: list[AgentEpisode] = []
        self.max_episodes = max_episodes

    def add_episode(self, episode: AgentEpisode) -> None:
        self.episodes.append(episode)
        if len(self.episodes) > self.max_episodes:
            self.episodes = self.episodes[-self.max_episodes:]

    def get_similar_episodes(self, goal: str, top_k: int = 3) -> list[AgentEpisode]:
        """In production, use embedding similarity. Here we use simple keyword match."""
        goal_words = set(goal.lower().split())
        scored = []
        for ep in self.episodes:
            if ep.status == AgentStatus.COMPLETED:
                ep_words = set(ep.goal.lower().split())
                overlap = len(goal_words & ep_words) / max(len(goal_words), 1)
                scored.append((overlap, ep))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:top_k]]


# ============================================================
# AGENT STATE
# ============================================================

@dataclass
class AgentState:
    episode: AgentEpisode = field(default_factory=AgentEpisode)
    working_memory: WorkingMemory = field(default_factory=WorkingMemory)
    token_budget: TokenBudget = field(default_factory=TokenBudget)
    current_step: int = 0


# ============================================================
# LLM CLIENT (PROTOCOL)
# ============================================================

class LLMResponse:
    def __init__(self, content: str, input_tokens: int = 0, output_tokens: int = 0):
        self.content = content
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class LLMClient(Protocol):
    def chat(self, messages: list[dict[str, str]], tools: list[dict] | None = None) -> LLMResponse:
        ...


# ============================================================
# MOCK LLM CLIENT (for demonstration)
# ============================================================

class MockLLMClient:
    """Simulates an LLM that follows the ReAct pattern."""

    def __init__(self):
        self.call_count = 0

    def chat(self, messages: list[dict[str, str]], tools: list[dict] | None = None) -> LLMResponse:
        self.call_count += 1

        # Simulate ReAct-style response
        if self.call_count == 1:
            return LLMResponse(
                content=json.dumps({
                    "reasoning": "I need to search for information about the user's query.",
                    "action": {
                        "type": "tool_call",
                        "tool_name": "web_search",
                        "tool_args": {"query": "example search"}
                    }
                }),
                input_tokens=500,
                output_tokens=100,
            )
        else:
            return LLMResponse(
                content=json.dumps({
                    "reasoning": "I have enough information to respond.",
                    "action": {
                        "type": "respond",
                        "response_text": "Based on my research, here is the answer..."
                    }
                }),
                input_tokens=800,
                output_tokens=150,
            )


# ============================================================
# OUTPUT PARSER
# ============================================================

class OutputParser:
    """Parses LLM output into structured AgentAction."""

    @staticmethod
    def parse(raw_output: str) -> AgentAction:
        """Parse JSON-structured LLM output into an AgentAction."""
        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError:
            # Fallback: treat entire output as a response
            return AgentAction(
                type=ActionType.RESPOND,
                response_text=raw_output,
                reasoning="[Failed to parse structured output, treating as direct response]",
            )

        reasoning = data.get("reasoning", "")
        action_data = data.get("action", {})
        action_type = ActionType(action_data.get("type", "respond"))

        return AgentAction(
            type=action_type,
            tool_name=action_data.get("tool_name"),
            tool_args=action_data.get("tool_args", {}),
            response_text=action_data.get("response_text"),
            reasoning=reasoning,
        )


# ============================================================
# TOOL REGISTRY
# ============================================================

class ToolRegistry:
    """Manages available tools and their execution."""

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def get_schemas(self) -> list[dict[str, Any]]:
        return [tool.to_schema() for tool in self._tools.values()]

    def execute(self, tool_name: str, args: dict[str, Any]) -> str:
        """Execute a tool with retry logic."""
        tool = self._tools.get(tool_name)
        if tool is None:
            raise ToolNotFoundError(f"Tool '{tool_name}' not found in registry")

        last_error: Exception | None = None
        for attempt in range(tool.max_retries + 1):
            try:
                start = time.time()
                result = tool.handler(**args)
                elapsed = time.time() - start
                if elapsed > tool.timeout_seconds:
                    raise ToolTimeoutError(f"Tool '{tool_name}' exceeded timeout of {tool.timeout_seconds}s")
                return str(result)
            except Exception as e:
                last_error = e
                if attempt < tool.max_retries:
                    time.sleep(0.5 * (attempt + 1))  # Exponential backoff
                    continue
                break

        raise ToolExecutionError(
            f"Tool '{tool_name}' failed after {tool.max_retries + 1} attempts: {last_error}"
        )


# ============================================================
# CUSTOM EXCEPTIONS
# ============================================================

class AgentError(Exception):
    pass

class ToolNotFoundError(AgentError):
    pass

class ToolExecutionError(AgentError):
    pass

class ToolTimeoutError(AgentError):
    pass

class GuardrailViolation(AgentError):
    pass

class BudgetExceededError(AgentError):
    pass

class MaxStepsExceededError(AgentError):
    pass

class AgentTimeoutError(AgentError):
    pass


# ============================================================
# THE AGENT
# ============================================================

class BasicReActAgent:
    """
    A production-grade ReAct agent with:
    - Full lifecycle management
    - Tool registry and execution with retries
    - Token budget tracking
    - Max steps and timeout enforcement
    - Pre/post action guardrails
    - Working memory and episode history
    - Structured output parsing
    - Error recovery
    """

    def __init__(
        self,
        llm_client: LLMClient,
        system_prompt: str,
        tools: list[ToolDefinition] | None = None,
        max_steps: int = 15,
        timeout_seconds: float = 300.0,
        token_budget: TokenBudget | None = None,
        pre_action_guardrails: list[PreActionGuardrail] | None = None,
        post_action_guardrails: list[PostActionGuardrail] | None = None,
        episode_history: EpisodeHistory | None = None,
    ):
        self.llm_client = llm_client
        self.system_prompt = system_prompt
        self.max_steps = max_steps
        self.timeout_seconds = timeout_seconds

        # Tool registry
        self.tool_registry = ToolRegistry()
        if tools:
            for tool in tools:
                self.tool_registry.register(tool)

        # Guardrails
        self.pre_guardrails = pre_action_guardrails or []
        self.post_guardrails = post_action_guardrails or []

        # Memory
        self.episode_history = episode_history or EpisodeHistory()

        # State
        self.state = AgentState(
            token_budget=token_budget or TokenBudget(),
        )

        # Output parser
        self.parser = OutputParser()

    # --------------------------------------------------------
    # PUBLIC API
    # --------------------------------------------------------

    def run(self, goal: str) -> AgentEpisode:
        """Execute the agent loop for a given goal. Returns the complete episode."""
        self._initialize_episode(goal)
        start_time = time.time()

        try:
            while self.state.current_step < self.max_steps:
                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > self.timeout_seconds:
                    self.state.episode.status = AgentStatus.TIMEOUT
                    self.state.episode.error = f"Agent timeout after {elapsed:.1f}s"
                    break

                # Check token budget
                if self.state.token_budget.is_exceeded():
                    self.state.episode.status = AgentStatus.BUDGET_EXCEEDED
                    self.state.episode.error = "Token budget exceeded"
                    break

                # Execute one step of the ReAct loop
                step = self._execute_step()

                # Check if agent decided to respond (terminate)
                if step.action.type == ActionType.RESPOND:
                    self.state.episode.status = AgentStatus.COMPLETED
                    self.state.episode.final_output = step.action.response_text
                    break
                elif step.action.type == ActionType.ESCALATE:
                    self.state.episode.status = AgentStatus.WAITING_FOR_HUMAN
                    self.state.episode.final_output = step.action.response_text
                    break

            else:
                # Loop exhausted without termination
                self.state.episode.status = AgentStatus.MAX_STEPS_EXCEEDED
                self.state.episode.error = f"Exceeded max steps ({self.max_steps})"

        except GuardrailViolation as e:
            self.state.episode.status = AgentStatus.FAILED
            self.state.episode.error = f"Guardrail violation: {e}"
        except Exception as e:
            self.state.episode.status = AgentStatus.FAILED
            self.state.episode.error = f"Unexpected error: {e}\n{traceback.format_exc()}"

        # Finalize
        self.state.episode.total_duration_ms = (time.time() - start_time) * 1000
        self.state.episode.total_tokens = self.state.token_budget.used_total
        self.episode_history.add_episode(self.state.episode)

        return self.state.episode

    # --------------------------------------------------------
    # INTERNAL METHODS
    # --------------------------------------------------------

    def _initialize_episode(self, goal: str) -> None:
        """Set up a fresh episode."""
        self.state = AgentState(
            episode=AgentEpisode(goal=goal, status=AgentStatus.RUNNING),
            working_memory=WorkingMemory(),
            token_budget=self.state.token_budget,
        )

    def _execute_step(self) -> AgentStep:
        """Execute a single Reason-Act-Observe cycle."""
        self.state.current_step += 1
        step_start = time.time()

        # 1. BUILD MESSAGES (context for LLM)
        messages = self._build_messages()

        # 2. CALL LLM (Reason + decide action)
        llm_response = self.llm_client.chat(
            messages=messages,
            tools=self.tool_registry.get_schemas() or None,
        )
        self.state.token_budget.record_usage(
            llm_response.input_tokens, llm_response.output_tokens
        )

        # 3. PARSE ACTION
        action = self.parser.parse(llm_response.content)

        # 4. EXECUTE ACTION (Act)
        observation = self._execute_action(action)

        # 5. RECORD STEP
        step = AgentStep(
            step_number=self.state.current_step,
            reasoning=action.reasoning,
            action=action,
            observation=observation,
            duration_ms=(time.time() - step_start) * 1000,
            tokens_used=llm_response.input_tokens + llm_response.output_tokens,
        )
        self.state.episode.steps.append(step)

        return step

    def _execute_action(self, action: AgentAction) -> Observation | None:
        """Execute the decided action and return observation."""
        if action.type == ActionType.RESPOND:
            return None
        if action.type == ActionType.ESCALATE:
            return None
        if action.type == ActionType.WAIT:
            return Observation(content="Waiting for external input.", source="system")

        if action.type == ActionType.TOOL_CALL:
            # Pre-action guardrails
            for guardrail in self.pre_guardrails:
                result = guardrail.check(action, self.state)
                if not result.allowed:
                    raise GuardrailViolation(result.reason)

            # Execute tool
            try:
                tool_result = self.tool_registry.execute(
                    action.tool_name, action.tool_args
                )
                observation = Observation(
                    content=tool_result,
                    source="tool",
                    metadata={"tool_name": action.tool_name, "args": action.tool_args},
                )
            except AgentError as e:
                observation = Observation(
                    content=f"ERROR: {e}",
                    source="error",
                    metadata={"tool_name": action.tool_name, "error_type": type(e).__name__},
                )

            # Post-action guardrails
            for guardrail in self.post_guardrails:
                guardrail.check(action, self.state)

            return observation

        return Observation(content=f"Unknown action type: {action.type}", source="system")

    def _build_messages(self) -> list[dict[str, str]]:
        """Build the message history for the LLM call."""
        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": f"Goal: {self.state.episode.goal}"},
        ]

        # Add step history
        for step in self.state.episode.steps:
            messages.append({
                "role": "assistant",
                "content": json.dumps({
                    "reasoning": step.reasoning,
                    "action": {
                        "type": step.action.type.value,
                        "tool_name": step.action.tool_name,
                        "tool_args": step.action.tool_args,
                    }
                }),
            })
            if step.observation:
                messages.append({
                    "role": "user",
                    "content": f"Observation: {step.observation.content}",
                })

        return messages

    def _build_system_prompt(self) -> str:
        """Construct system prompt with context."""
        parts = [
            self.system_prompt,
            "\n\n## Available Tools\n",
        ]

        for tool in self.tool_registry.list_tools():
            parts.append(f"- **{tool.name}**: {tool.description}")

        # Add working memory context
        memory_context = self.state.working_memory.to_context_string()
        if memory_context:
            parts.append(f"\n\n## Current Context\n{memory_context}")

        # Add similar past episodes as few-shot
        similar = self.episode_history.get_similar_episodes(self.state.episode.goal, top_k=2)
        if similar:
            parts.append("\n\n## Relevant Past Experiences")
            for ep in similar:
                parts.append(f"- Goal: '{ep.goal}' → Completed in {len(ep.steps)} steps")

        parts.append(f"""

## Response Format
Respond with JSON:
{{
  "reasoning": "your chain-of-thought reasoning",
  "action": {{
    "type": "tool_call|respond|escalate|wait",
    "tool_name": "name (if tool_call)",
    "tool_args": {{...}} ,
    "response_text": "final answer (if respond/escalate)"
  }}
}}

## Rules
- Step {self.state.current_step}/{self.max_steps} (remaining: {self.max_steps - self.state.current_step})
- Token budget remaining: {self.state.token_budget.remaining}
- Think step by step. Explain your reasoning before acting.
- If you have enough information, respond. Do not over-research.
- If you encounter an error, try an alternative approach.
- If you cannot complete the task, escalate with explanation.
""")
        return "\n".join(parts)


# ============================================================
# EXAMPLE USAGE
# ============================================================

def example_web_search(query: str) -> str:
    """Simulated web search tool."""
    return f"Search results for '{query}': [Result 1: Example content, Result 2: More content]"


def example_calculator(expression: str) -> str:
    """Simulated calculator tool."""
    try:
        result = eval(expression)  # In production, use a safe math parser
        return str(result)
    except Exception as e:
        return f"Error: {e}"


def main():
    """Demonstrate the basic ReAct agent."""
    # Define tools
    tools = [
        ToolDefinition(
            name="web_search",
            description="Search the web for information. Use for factual queries.",
            parameters=[
                ToolParameter(name="query", type="string", description="The search query"),
            ],
            handler=example_web_search,
        ),
        ToolDefinition(
            name="calculator",
            description="Evaluate a mathematical expression.",
            parameters=[
                ToolParameter(name="expression", type="string", description="Math expression to evaluate"),
            ],
            handler=example_calculator,
        ),
    ]

    # Define guardrails
    guardrails = [
        CostLimitGuardrail(max_cost_usd=1.00),
    ]

    # Create agent
    agent = BasicReActAgent(
        llm_client=MockLLMClient(),
        system_prompt="You are a helpful research assistant. Answer questions accurately and concisely.",
        tools=tools,
        max_steps=10,
        timeout_seconds=60.0,
        token_budget=TokenBudget(max_total_tokens=50_000),
        pre_action_guardrails=guardrails,
    )

    # Run agent
    episode = agent.run("What is the population of Tokyo and how does it compare to New York?")

    # Print results
    print(f"\n{'='*60}")
    print(f"Episode: {episode.episode_id}")
    print(f"Goal: {episode.goal}")
    print(f"Status: {episode.status.value}")
    print(f"Steps: {len(episode.steps)}")
    print(f"Tokens: {episode.total_tokens}")
    print(f"Duration: {episode.total_duration_ms:.0f}ms")
    print(f"Output: {episode.final_output}")
    print(f"{'='*60}")

    for step in episode.steps:
        print(f"\n  Step {step.step_number}:")
        print(f"    Reasoning: {step.reasoning}")
        print(f"    Action: {step.action.type.value} → {step.action.tool_name or 'respond'}")
        if step.observation:
            print(f"    Observation: {step.observation.content[:100]}...")


if __name__ == "__main__":
    main()
