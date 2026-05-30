"""
IMPLEMENTATION: Advanced Prompt Engineering
=============================================
Production-grade prompt engineering patterns including:
system prompt design, few-shot optimization, chain-of-thought,
versioning, regression testing, template engine, and context budget management.
"""

import json
import hashlib
import re
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from string import Template

import tiktoken
from pydantic import BaseModel, Field
from openai import OpenAI


# =============================================================================
# 1. SYSTEM PROMPT DESIGN PATTERNS
# =============================================================================

class SystemPromptBuilder:
    """
    Builder pattern for constructing well-structured system prompts.
    
    Architecture: A good system prompt has these sections:
    1. Identity/Role — WHO the model is
    2. Capabilities — WHAT it can do
    3. Constraints — WHAT it must NOT do
    4. Output format — HOW to respond
    5. Examples — WHAT good output looks like
    """

    def __init__(self):
        self._sections: list[tuple[str, str]] = []

    def identity(self, role: str) -> "SystemPromptBuilder":
        """Define the model's role and persona."""
        self._sections.append(("IDENTITY", role))
        return self

    def capabilities(self, caps: list[str]) -> "SystemPromptBuilder":
        """Define what the model can do."""
        formatted = "\n".join(f"- {c}" for c in caps)
        self._sections.append(("CAPABILITIES", f"You can:\n{formatted}"))
        return self

    def constraints(self, rules: list[str]) -> "SystemPromptBuilder":
        """Define hard boundaries (MUST/MUST NOT rules)."""
        formatted = "\n".join(f"- {r}" for r in rules)
        self._sections.append(("CONSTRAINTS", f"You MUST follow these rules:\n{formatted}"))
        return self

    def output_format(self, format_spec: str) -> "SystemPromptBuilder":
        """Define expected output format."""
        self._sections.append(("OUTPUT FORMAT", format_spec))
        return self

    def context(self, context: str) -> "SystemPromptBuilder":
        """Add domain context or background information."""
        self._sections.append(("CONTEXT", context))
        return self

    def examples(self, examples: list[dict]) -> "SystemPromptBuilder":
        """Add few-shot examples to the system prompt."""
        formatted = ""
        for i, ex in enumerate(examples, 1):
            formatted += f"\nExample {i}:\nInput: {ex['input']}\nOutput: {ex['output']}\n"
        self._sections.append(("EXAMPLES", formatted))
        return self

    def build(self) -> str:
        """Assemble the final system prompt."""
        parts = []
        for section_name, content in self._sections:
            parts.append(f"## {section_name}\n{content}")
        return "\n\n".join(parts)


# Pre-built system prompt patterns for common use cases

SYSTEM_PROMPTS = {
    "data_extractor": SystemPromptBuilder()
        .identity("You are a precise data extraction engine.")
        .constraints([
            "Extract ONLY information explicitly stated in the input",
            "Never infer or assume information not present",
            "Use null for fields where information is not available",
            "Never add explanatory text outside the JSON structure",
        ])
        .output_format("Output valid JSON matching the provided schema. Nothing else.")
        .build(),

    "code_reviewer": SystemPromptBuilder()
        .identity("You are a senior software engineer conducting code reviews.")
        .capabilities([
            "Identify bugs, security vulnerabilities, and performance issues",
            "Suggest improvements with concrete code examples",
            "Explain the reasoning behind each suggestion",
        ])
        .constraints([
            "Focus on actionable feedback only",
            "Do not comment on style preferences unless they affect readability",
            "Rate severity: critical > major > minor > nitpick",
            "Limit to 5 most important issues",
        ])
        .output_format(
            "For each issue:\n"
            "1. **[SEVERITY]** One-line description\n"
            "2. Location (file:line)\n"
            "3. Why it's a problem\n"
            "4. Suggested fix (code)"
        )
        .build(),

    "conversational_assistant": SystemPromptBuilder()
        .identity("You are a helpful, knowledgeable assistant.")
        .constraints([
            "Be concise — prefer short answers unless detail is requested",
            "Acknowledge uncertainty — say 'I'm not sure' when appropriate",
            "Never fabricate citations, URLs, or specific statistics",
            "Ask clarifying questions when the request is ambiguous",
        ])
        .build(),
}


# =============================================================================
# 2. FEW-SHOT PROMPT OPTIMIZATION
# =============================================================================

@dataclass
class FewShotExample:
    """A single few-shot example with metadata for selection."""
    input: str
    output: str
    category: str = "general"
    difficulty: str = "medium"  # easy, medium, hard
    tokens: int = 0  # Pre-computed token count


class FewShotOptimizer:
    """
    Selects the optimal few-shot examples for a given query.
    
    Strategies:
    - Similarity-based: Pick examples most similar to the input
    - Diversity-based: Cover different aspects of the task
    - Difficulty-based: Match input complexity to example complexity
    - Budget-aware: Fit within token budget
    """

    def __init__(self, examples: list[FewShotExample], model: str = "gpt-4o"):
        self.examples = examples
        self.encoder = tiktoken.encoding_for_model(model)
        # Pre-compute token counts
        for ex in self.examples:
            ex.tokens = len(self.encoder.encode(ex.input + ex.output))

    def select_examples(
        self,
        query: str,
        max_examples: int = 5,
        max_tokens: int = 2000,
        strategy: str = "diversity",
    ) -> list[FewShotExample]:
        """Select optimal examples within token budget."""

        if strategy == "diversity":
            return self._select_diverse(query, max_examples, max_tokens)
        elif strategy == "similar":
            return self._select_similar(query, max_examples, max_tokens)
        else:
            # Simple: first N that fit in budget
            selected = []
            total_tokens = 0
            for ex in self.examples[:max_examples]:
                if total_tokens + ex.tokens <= max_tokens:
                    selected.append(ex)
                    total_tokens += ex.tokens
            return selected

    def _select_diverse(self, query: str, max_examples: int, max_tokens: int) -> list[FewShotExample]:
        """Select examples covering different categories."""
        by_category: dict[str, list[FewShotExample]] = {}
        for ex in self.examples:
            by_category.setdefault(ex.category, []).append(ex)

        selected = []
        total_tokens = 0
        categories = list(by_category.keys())

        # Round-robin across categories
        idx = 0
        while len(selected) < max_examples and idx < len(self.examples):
            cat = categories[idx % len(categories)]
            if by_category[cat]:
                ex = by_category[cat].pop(0)
                if total_tokens + ex.tokens <= max_tokens:
                    selected.append(ex)
                    total_tokens += ex.tokens
            idx += 1

        return selected

    def _select_similar(self, query: str, max_examples: int, max_tokens: int) -> list[FewShotExample]:
        """Select examples with highest keyword overlap to query."""
        query_words = set(query.lower().split())

        scored = []
        for ex in self.examples:
            ex_words = set(ex.input.lower().split())
            overlap = len(query_words & ex_words) / max(len(query_words), 1)
            scored.append((overlap, ex))

        scored.sort(key=lambda x: x[0], reverse=True)

        selected = []
        total_tokens = 0
        for _, ex in scored:
            if len(selected) >= max_examples:
                break
            if total_tokens + ex.tokens <= max_tokens:
                selected.append(ex)
                total_tokens += ex.tokens

        return selected

    def format_examples(self, examples: list[FewShotExample]) -> str:
        """Format selected examples into prompt text."""
        parts = []
        for i, ex in enumerate(examples, 1):
            parts.append(f"Example {i}:\nInput: {ex.input}\nOutput: {ex.output}")
        return "\n\n".join(parts)


# =============================================================================
# 3. CHAIN-OF-THOUGHT PROMPTING
# =============================================================================

class ChainOfThought:
    """
    Chain-of-thought (CoT) prompting patterns.
    
    CoT makes the model "think step by step" before answering,
    dramatically improving accuracy on reasoning tasks.
    """

    @staticmethod
    def zero_shot_cot(question: str) -> str:
        """
        Zero-shot CoT: Just append "Let's think step by step."
        Surprisingly effective without any examples.
        """
        return f"{question}\n\nLet's think step by step."

    @staticmethod
    def structured_cot(question: str, steps: list[str] = None) -> str:
        """
        Structured CoT: Guide the model through specific reasoning steps.
        More reliable than freeform CoT for complex tasks.
        """
        if steps is None:
            steps = [
                "First, identify the key information given",
                "Second, determine what we need to find",
                "Third, plan the approach",
                "Fourth, execute step by step",
                "Finally, verify the answer",
            ]

        steps_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
        return f"{question}\n\nThink through this systematically:\n{steps_text}"

    @staticmethod
    def self_consistency(question: str, n_paths: int = 3) -> str:
        """
        Self-consistency: Generate multiple reasoning paths and pick the majority answer.
        Requires multiple API calls with temperature > 0.
        
        This is implemented at the orchestration level, not in the prompt.
        Returns the prompt for a single path.
        """
        return (
            f"{question}\n\n"
            "Solve this problem. Show your complete reasoning process. "
            "At the end, clearly state your final answer on its own line prefixed with 'ANSWER: '"
        )

    @staticmethod
    def react_prompt(question: str, available_tools: list[str]) -> str:
        """
        ReAct pattern: Interleave Reasoning and Acting.
        The model thinks, acts (tool call), observes result, repeats.
        """
        tools_desc = "\n".join(f"- {t}" for t in available_tools)
        return (
            f"Answer the following question using the available tools.\n\n"
            f"Question: {question}\n\n"
            f"Available tools:\n{tools_desc}\n\n"
            f"Use this format:\n"
            f"Thought: [your reasoning about what to do next]\n"
            f"Action: [tool name]\n"
            f"Action Input: [input to the tool]\n"
            f"Observation: [result from the tool]\n"
            f"... (repeat as needed)\n"
            f"Thought: I now have enough information to answer.\n"
            f"Final Answer: [your answer]"
        )


# =============================================================================
# 4. PROMPT VERSIONING SYSTEM
# =============================================================================

@dataclass
class PromptVersion:
    """A versioned prompt with metadata for tracking changes."""
    id: str
    version: str
    content: str
    author: str
    created_at: datetime = field(default_factory=datetime.now)
    description: str = ""
    metrics: dict = field(default_factory=dict)  # Performance metrics from evaluation
    is_active: bool = False

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()[:12]


class PromptRegistry:
    """
    Production prompt management system.
    
    Features:
    - Version tracking with content hashing
    - A/B testing support
    - Rollback capability
    - Performance metrics per version
    
    In production, back this with a database (PostgreSQL, DynamoDB).
    """

    def __init__(self):
        self._prompts: dict[str, list[PromptVersion]] = {}  # id -> [versions]
        self._active: dict[str, PromptVersion] = {}  # id -> active version

    def register(self, prompt_id: str, content: str, author: str, description: str = "") -> PromptVersion:
        """Register a new version of a prompt."""
        versions = self._prompts.setdefault(prompt_id, [])
        version_num = f"v{len(versions) + 1}"

        version = PromptVersion(
            id=prompt_id,
            version=version_num,
            content=content,
            author=author,
            description=description,
        )
        versions.append(version)
        return version

    def activate(self, prompt_id: str, version: str = None):
        """Set the active version for a prompt. Defaults to latest."""
        versions = self._prompts.get(prompt_id, [])
        if not versions:
            raise ValueError(f"No prompt with id '{prompt_id}'")

        if version:
            target = next((v for v in versions if v.version == version), None)
            if not target:
                raise ValueError(f"Version '{version}' not found")
        else:
            target = versions[-1]

        # Deactivate current
        if prompt_id in self._active:
            self._active[prompt_id].is_active = False

        target.is_active = True
        self._active[prompt_id] = target

    def get(self, prompt_id: str) -> str:
        """Get the active version of a prompt."""
        if prompt_id not in self._active:
            raise ValueError(f"No active prompt for '{prompt_id}'")
        return self._active[prompt_id].content

    def rollback(self, prompt_id: str):
        """Roll back to the previous version."""
        versions = self._prompts.get(prompt_id, [])
        current = self._active.get(prompt_id)
        if not current or len(versions) < 2:
            raise ValueError("Cannot rollback")

        current_idx = versions.index(current)
        if current_idx == 0:
            raise ValueError("Already at first version")

        self.activate(prompt_id, versions[current_idx - 1].version)

    def record_metrics(self, prompt_id: str, metrics: dict):
        """Record performance metrics for the active version."""
        if prompt_id in self._active:
            self._active[prompt_id].metrics.update(metrics)

    def get_history(self, prompt_id: str) -> list[dict]:
        """Get version history with metrics."""
        return [
            {
                "version": v.version,
                "hash": v.content_hash,
                "author": v.author,
                "created_at": v.created_at.isoformat(),
                "is_active": v.is_active,
                "metrics": v.metrics,
                "description": v.description,
            }
            for v in self._prompts.get(prompt_id, [])
        ]


# =============================================================================
# 5. PROMPT REGRESSION TESTING
# =============================================================================

@dataclass
class PromptTestCase:
    """A test case for prompt regression testing."""
    input: str
    expected_contains: list[str] = field(default_factory=list)  # Must contain these strings
    expected_not_contains: list[str] = field(default_factory=list)  # Must NOT contain these
    expected_format: Optional[str] = None  # "json", "markdown", "list"
    max_tokens: Optional[int] = None  # Output should not exceed this


@dataclass
class PromptTestResult:
    """Result of a single prompt test."""
    passed: bool
    failures: list[str] = field(default_factory=list)
    output: str = ""
    latency_ms: float = 0


class PromptRegressionSuite:
    """
    Automated regression testing for prompts.
    
    Run this before deploying any prompt change to production.
    Catches: format changes, missing content, unexpected behavior.
    """

    def __init__(self, model: str = "gpt-4o"):
        self.model = model
        self.client = OpenAI()

    def run_test(self, system_prompt: str, test_case: PromptTestCase) -> PromptTestResult:
        """Run a single test case against a prompt."""
        import time
        start = time.time()

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": test_case.input},
            ],
            temperature=0,
            max_tokens=test_case.max_tokens or 1024,
        )

        output = response.choices[0].message.content
        elapsed = (time.time() - start) * 1000
        failures = []

        # Check required content
        for required in test_case.expected_contains:
            if required.lower() not in output.lower():
                failures.append(f"Missing required content: '{required}'")

        # Check forbidden content
        for forbidden in test_case.expected_not_contains:
            if forbidden.lower() in output.lower():
                failures.append(f"Contains forbidden content: '{forbidden}'")

        # Check format
        if test_case.expected_format == "json":
            try:
                json.loads(output)
            except json.JSONDecodeError:
                failures.append("Expected valid JSON output")
        elif test_case.expected_format == "markdown":
            if not any(marker in output for marker in ["#", "-", "*", "```"]):
                failures.append("Expected markdown formatting")

        return PromptTestResult(
            passed=len(failures) == 0,
            failures=failures,
            output=output,
            latency_ms=elapsed,
        )

    def run_suite(self, system_prompt: str, test_cases: list[PromptTestCase]) -> dict:
        """Run full test suite and return summary."""
        results = [self.run_test(system_prompt, tc) for tc in test_cases]

        passed = sum(1 for r in results if r.passed)
        return {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "pass_rate": passed / len(results) if results else 0,
            "avg_latency_ms": sum(r.latency_ms for r in results) / len(results) if results else 0,
            "failures": [
                {"input": tc.input, "failures": r.failures}
                for tc, r in zip(test_cases, results)
                if not r.passed
            ],
        }


# =============================================================================
# 6. TEMPLATE ENGINE FOR DYNAMIC PROMPTS
# =============================================================================

class PromptTemplate:
    """
    A template engine for dynamic prompt construction.
    
    Supports:
    - Variable substitution ({{ variable }})
    - Conditional sections ({% if condition %})
    - Loops ({% for item in items %})
    - Token counting for budget management
    
    Simpler than Jinja2 but purpose-built for prompts.
    """

    def __init__(self, template: str, model: str = "gpt-4o"):
        self.template = template
        self.encoder = tiktoken.encoding_for_model(model)

    def render(self, **kwargs) -> str:
        """Render the template with provided variables."""
        result = self.template

        # Handle conditionals: {% if var %}content{% endif %}
        def replace_conditional(match):
            var_name = match.group(1).strip()
            content = match.group(2)
            if kwargs.get(var_name):
                return content
            return ""

        result = re.sub(
            r'\{%\s*if\s+(\w+)\s*%\}(.*?)\{%\s*endif\s*%\}',
            replace_conditional,
            result,
            flags=re.DOTALL,
        )

        # Handle loops: {% for item in items %}...{{ item }}...{% endfor %}
        def replace_loop(match):
            var_name = match.group(1).strip()
            collection_name = match.group(2).strip()
            body = match.group(3)
            collection = kwargs.get(collection_name, [])
            parts = []
            for item in collection:
                parts.append(body.replace(f"{{{{ {var_name} }}}}", str(item)))
            return "\n".join(parts)

        result = re.sub(
            r'\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}(.*?)\{%\s*endfor\s*%\}',
            replace_loop,
            result,
            flags=re.DOTALL,
        )

        # Handle variable substitution: {{ variable }}
        for key, value in kwargs.items():
            result = result.replace(f"{{{{ {key} }}}}", str(value))

        return result

    def count_tokens(self, **kwargs) -> int:
        """Count tokens in the rendered template."""
        rendered = self.render(**kwargs)
        return len(self.encoder.encode(rendered))


# Pre-built templates
TEMPLATES = {
    "rag_qa": PromptTemplate("""Answer the user's question based ONLY on the provided context.
If the context doesn't contain enough information, say "I don't have enough information to answer that."

{% if context %}
## Context
{% for chunk in context_chunks %}
---
{{ chunk }}
{% endfor %}
{% endif %}

## Question
{{ question }}

## Instructions
- Cite specific parts of the context that support your answer
- Do not use external knowledge
{% if output_format %}- Format your response as: {{ output_format }}{% endif %}"""),

    "classification": PromptTemplate("""Classify the following text into one of these categories: {{ categories }}

{% if examples %}
## Examples
{% for example in examples %}
Text: "{{ example }}"
{% endfor %}
{% endif %}

## Text to classify
{{ text }}

Output ONLY the category name, nothing else."""),
}


# =============================================================================
# 7. CONTEXT WINDOW BUDGET MANAGEMENT
# =============================================================================

class ContextBudget:
    """
    Manages token budget allocation across different context sections.
    
    This is CRITICAL for production systems. Without budget management,
    you'll hit context limits and get truncated outputs or errors.
    
    Architecture:
    - Total budget = model's context window - reserved output tokens
    - Budget is allocated to sections by priority
    - Lower-priority sections get truncated/dropped when budget is tight
    """

    def __init__(self, model: str = "gpt-4o", max_output_tokens: int = 4096):
        self.model = model
        self.encoder = tiktoken.encoding_for_model(model)

        # Model context windows
        context_windows = {
            "gpt-4o": 128_000,
            "gpt-4o-mini": 128_000,
            "gpt-4-turbo": 128_000,
            "claude-3-5-sonnet-20241022": 200_000,
            "claude-3-5-haiku-20241022": 200_000,
        }

        self.total_budget = context_windows.get(model, 128_000) - max_output_tokens
        self.allocations: dict[str, dict] = {}
        self._used: dict[str, int] = {}

    def allocate(self, section: str, max_tokens: int = None, priority: int = 1, required: bool = False):
        """
        Allocate budget for a context section.
        
        Priority: 1 = highest (always included), 5 = lowest (dropped first)
        Required: If True, raises error if section cannot fit.
        """
        self.allocations[section] = {
            "max_tokens": max_tokens or self.total_budget,
            "priority": priority,
            "required": required,
        }

    def fit_content(self, sections: dict[str, str]) -> dict[str, str]:
        """
        Fit content into the budget, truncating/dropping by priority.
        
        Returns the content that fits within budget, respecting priorities.
        """
        # Calculate token counts for each section
        section_tokens = {}
        for name, content in sections.items():
            section_tokens[name] = len(self.encoder.encode(content))

        # Sort by priority (1 = highest priority, include first)
        sorted_sections = sorted(
            sections.keys(),
            key=lambda s: self.allocations.get(s, {}).get("priority", 3),
        )

        result = {}
        remaining_budget = self.total_budget

        for section_name in sorted_sections:
            if section_name not in sections:
                continue

            content = sections[section_name]
            tokens = section_tokens[section_name]
            alloc = self.allocations.get(section_name, {"max_tokens": self.total_budget, "priority": 3, "required": False})
            max_allowed = min(alloc["max_tokens"], remaining_budget)

            if tokens <= max_allowed:
                # Fits entirely
                result[section_name] = content
                remaining_budget -= tokens
            elif alloc["required"]:
                # Must include — truncate to fit
                result[section_name] = self._truncate_to_tokens(content, max_allowed)
                remaining_budget -= max_allowed
            elif max_allowed > 100:
                # Optional but has room — include truncated
                result[section_name] = self._truncate_to_tokens(content, max_allowed)
                remaining_budget -= min(tokens, max_allowed)
            # else: drop this section entirely

        self._used = {name: len(self.encoder.encode(content)) for name, content in result.items()}
        return result

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token limit."""
        tokens = self.encoder.encode(text)
        if len(tokens) <= max_tokens:
            return text
        truncated_tokens = tokens[:max_tokens - 10]  # Leave room for truncation marker
        return self.encoder.decode(truncated_tokens) + "\n[...truncated]"

    def get_usage_report(self) -> dict:
        """Report on budget utilization."""
        return {
            "total_budget": self.total_budget,
            "used": sum(self._used.values()),
            "remaining": self.total_budget - sum(self._used.values()),
            "utilization_pct": round(sum(self._used.values()) / self.total_budget * 100, 1),
            "sections": {name: {"tokens": tokens, "pct": round(tokens / self.total_budget * 100, 1)} for name, tokens in self._used.items()},
        }


# =============================================================================
# USAGE EXAMPLES
# =============================================================================

if __name__ == "__main__":
    # --- System Prompt Builder ---
    print("=== System Prompt ===")
    prompt = (SystemPromptBuilder()
        .identity("You are a customer support agent for Acme Corp.")
        .capabilities(["Look up order status", "Process refunds up to $100", "Escalate to human agent"])
        .constraints(["Never share internal system details", "Always verify customer identity first", "Be empathetic but concise"])
        .output_format("Use markdown. Start with a greeting. End with 'Is there anything else I can help with?'")
        .build())
    print(prompt[:500])

    # --- Template Engine ---
    print("\n=== Template Rendering ===")
    template = TEMPLATES["rag_qa"]
    rendered = template.render(
        context=True,
        context_chunks=["Revenue grew 15% in Q3.", "Operating expenses decreased 5%."],
        question="How did the company perform financially?",
        output_format="bullet points",
    )
    print(rendered[:500])
    print(f"Token count: {template.count_tokens(context=True, context_chunks=['chunk1', 'chunk2'], question='test', output_format='json')}")

    # --- Context Budget ---
    print("\n=== Context Budget ===")
    budget = ContextBudget(model="gpt-4o", max_output_tokens=4096)
    budget.allocate("system_prompt", max_tokens=2000, priority=1, required=True)
    budget.allocate("tools", max_tokens=1000, priority=1, required=True)
    budget.allocate("rag_context", max_tokens=8000, priority=2)
    budget.allocate("conversation_history", max_tokens=4000, priority=3)
    budget.allocate("user_message", max_tokens=2000, priority=1, required=True)

    fitted = budget.fit_content({
        "system_prompt": "You are a helpful assistant. " * 50,
        "tools": json.dumps([{"name": "search", "params": {}}]),
        "rag_context": "Relevant document content. " * 500,
        "conversation_history": "User: Hi\nAssistant: Hello! " * 100,
        "user_message": "What is the refund policy?",
    })

    print(json.dumps(budget.get_usage_report(), indent=2))

    # --- Prompt Versioning ---
    print("\n=== Prompt Versioning ===")
    registry = PromptRegistry()
    registry.register("support_agent", "You are a support agent. Be helpful.", "alice", "Initial version")
    registry.register("support_agent", "You are a support agent. Be helpful and concise.", "bob", "Added conciseness")
    registry.activate("support_agent")
    print(f"Active prompt: {registry.get('support_agent')}")
    print(f"History: {json.dumps(registry.get_history('support_agent'), indent=2, default=str)}")
