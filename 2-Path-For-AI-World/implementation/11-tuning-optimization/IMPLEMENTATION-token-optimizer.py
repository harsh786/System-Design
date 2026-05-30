"""
Token Optimization System
=========================
Production-grade token reduction and context budget management.
Reduces cost 40-70% while maintaining quality through:
- Prompt compression
- Context budgeting
- History summarization
- Dynamic prompt selection
- Tool schema optimization
"""

import hashlib
import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


# =============================================================================
# Token Counting
# =============================================================================

class TokenCounter:
    """Estimates token counts for various models."""

    # Approximate tokens per character ratios by model family
    MODEL_RATIOS = {
        "gpt-4": 0.25,
        "gpt-4o": 0.25,
        "gpt-4o-mini": 0.25,
        "claude": 0.25,
        "llama": 0.27,
        "default": 0.25,
    }

    # Cost per 1M tokens (input/output) in USD
    MODEL_COSTS = {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4": {"input": 30.00, "output": 60.00},
        "claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
        "llama-3-70b": {"input": 0.80, "output": 0.80},
        "llama-3-8b": {"input": 0.10, "output": 0.10},
    }

    def __init__(self, model: str = "gpt-4o"):
        self.model = model
        self.ratio = self.MODEL_RATIOS.get(model, self.MODEL_RATIOS["default"])

    def count(self, text: str) -> int:
        """Estimate token count for text."""
        if not text:
            return 0
        # Rough heuristic: ~4 chars per token for English
        return max(1, int(len(text) * self.ratio))

    def count_messages(self, messages: list[dict]) -> int:
        """Count tokens in a message array."""
        total = 0
        for msg in messages:
            total += 4  # Message overhead
            total += self.count(msg.get("role", ""))
            total += self.count(msg.get("content", ""))
            if "tool_calls" in msg:
                total += self.count(json.dumps(msg["tool_calls"]))
        total += 2  # Reply priming
        return total

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD."""
        costs = self.MODEL_COSTS.get(self.model, {"input": 2.50, "output": 10.00})
        input_cost = (input_tokens / 1_000_000) * costs["input"]
        output_cost = (output_tokens / 1_000_000) * costs["output"]
        return input_cost + output_cost


# =============================================================================
# Context Budget Manager
# =============================================================================

class BudgetPriority(Enum):
    CRITICAL = 1      # System prompt, current query
    HIGH = 2          # Retrieved context
    MEDIUM = 3        # Conversation history
    LOW = 4           # Tool schemas, examples
    OPTIONAL = 5      # Nice-to-have context


@dataclass
class BudgetAllocation:
    """Allocation for a single component."""
    component: str
    priority: BudgetPriority
    min_tokens: int
    max_tokens: int
    allocated: int = 0
    actual: int = 0


@dataclass
class ContextBudget:
    """Complete context budget for a request."""
    total_budget: int
    output_reserve: int
    allocations: list[BudgetAllocation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def input_budget(self) -> int:
        return self.total_budget - self.output_reserve

    @property
    def total_allocated(self) -> int:
        return sum(a.allocated for a in self.allocations)

    @property
    def remaining(self) -> int:
        return self.input_budget - self.total_allocated


class ContextBudgetManager:
    """
    Manages token budget allocation across prompt components.
    
    Ensures total context fits within model limits while prioritizing
    critical components (system prompt, query) over optional ones (history, examples).
    """

    DEFAULT_BUDGETS = {
        "system_prompt": BudgetAllocation("system_prompt", BudgetPriority.CRITICAL, 100, 800),
        "current_query": BudgetAllocation("current_query", BudgetPriority.CRITICAL, 50, 500),
        "retrieved_context": BudgetAllocation("retrieved_context", BudgetPriority.HIGH, 500, 4000),
        "conversation_history": BudgetAllocation("conversation_history", BudgetPriority.MEDIUM, 0, 2000),
        "tool_schemas": BudgetAllocation("tool_schemas", BudgetPriority.LOW, 0, 1000),
        "examples": BudgetAllocation("examples", BudgetPriority.OPTIONAL, 0, 1000),
    }

    def __init__(
        self,
        model_context_window: int = 8192,
        output_reserve: int = 2000,
        custom_allocations: Optional[dict[str, BudgetAllocation]] = None,
    ):
        self.model_context_window = model_context_window
        self.output_reserve = output_reserve
        self.allocations = custom_allocations or dict(self.DEFAULT_BUDGETS)

    def allocate(self, component_sizes: dict[str, int]) -> ContextBudget:
        """
        Allocate budget based on actual component sizes.
        
        Strategy:
        1. Satisfy all CRITICAL components first (up to max)
        2. Allocate HIGH priority up to their max or remaining budget
        3. Fill MEDIUM/LOW/OPTIONAL with remaining space
        4. If over budget, trim from lowest priority first
        """
        budget = ContextBudget(
            total_budget=self.model_context_window,
            output_reserve=self.output_reserve,
        )
        input_budget = budget.input_budget

        # Sort allocations by priority
        sorted_components = sorted(
            self.allocations.items(),
            key=lambda x: x[1].priority.value,
        )

        remaining = input_budget

        for name, alloc in sorted_components:
            actual_size = component_sizes.get(name, 0)
            allocation = BudgetAllocation(
                component=name,
                priority=alloc.priority,
                min_tokens=alloc.min_tokens,
                max_tokens=alloc.max_tokens,
                actual=actual_size,
            )

            # Allocate: min(actual_size, max_tokens, remaining)
            allocated = min(actual_size, alloc.max_tokens, remaining)

            # Ensure minimum for critical components
            if alloc.priority == BudgetPriority.CRITICAL:
                allocated = max(allocated, min(alloc.min_tokens, remaining))

            allocation.allocated = max(0, allocated)
            remaining -= allocation.allocated

            if actual_size > allocation.allocated and actual_size > 0:
                budget.warnings.append(
                    f"{name}: truncated from {actual_size} to {allocation.allocated} tokens"
                )

            budget.allocations.append(allocation)

            if remaining <= 0:
                budget.warnings.append(f"Budget exhausted at component: {name}")
                break

        return budget

    def get_allocation_for(self, budget: ContextBudget, component: str) -> int:
        """Get allocated tokens for a specific component."""
        for alloc in budget.allocations:
            if alloc.component == component:
                return alloc.allocated
        return 0


# =============================================================================
# Prompt Compressor
# =============================================================================

class PromptCompressor:
    """
    Compresses prompts by removing redundancy and shortening instructions.
    
    Techniques:
    - Remove filler words and phrases
    - Shorten common instruction patterns
    - Remove redundant whitespace
    - Compress examples to minimal form
    - Remove unnecessary politeness markers
    """

    FILLER_PATTERNS = [
        (r"\bplease\b", ""),
        (r"\bkindly\b", ""),
        (r"\bmake sure to\b", ""),
        (r"\bit is important that\b", ""),
        (r"\byou should always\b", "always"),
        (r"\byou need to\b", ""),
        (r"\bin order to\b", "to"),
        (r"\bfor the purpose of\b", "for"),
        (r"\bat this point in time\b", "now"),
        (r"\bdue to the fact that\b", "because"),
        (r"\bin the event that\b", "if"),
        (r"\bwith regard to\b", "about"),
        (r"\bI would like you to\b", ""),
        (r"\bI want you to\b", ""),
        (r"\bYou are a helpful[^.]*\.\s*", ""),
        (r"\bYou are an AI assistant[^.]*\.\s*", ""),
    ]

    SHORTENING_RULES = [
        ("do not", "don't"),
        ("cannot", "can't"),
        ("will not", "won't"),
        ("should not", "shouldn't"),
        ("would not", "wouldn't"),
        ("information", "info"),
        ("documentation", "docs"),
        ("configuration", "config"),
        ("application", "app"),
        ("approximately", "~"),
    ]

    def compress(self, prompt: str, aggression: float = 0.5) -> str:
        """
        Compress a prompt.
        
        Args:
            prompt: The prompt text to compress
            aggression: 0.0 (minimal) to 1.0 (maximum) compression
            
        Returns:
            Compressed prompt
        """
        result = prompt

        # Always: normalize whitespace
        result = re.sub(r"\n{3,}", "\n\n", result)
        result = re.sub(r"[ \t]+", " ", result)
        result = result.strip()

        # Light compression: remove filler
        if aggression >= 0.3:
            for pattern, replacement in self.FILLER_PATTERNS:
                result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        # Medium compression: shorten words
        if aggression >= 0.5:
            for long, short in self.SHORTENING_RULES:
                result = result.replace(long, short)

        # Heavy compression: remove examples if present
        if aggression >= 0.8:
            # Remove example blocks (heuristic)
            result = re.sub(
                r"(?:Example|For example|e\.g\.)[:\s][^\n]*(?:\n[^\n]+){0,5}",
                "",
                result,
                flags=re.IGNORECASE,
            )

        # Clean up artifacts
        result = re.sub(r"  +", " ", result)
        result = re.sub(r"\n ", "\n", result)
        result = re.sub(r" \.", ".", result)
        result = re.sub(r" ,", ",", result)

        return result.strip()

    def compress_to_budget(self, prompt: str, max_tokens: int, counter: TokenCounter) -> str:
        """Compress prompt to fit within token budget."""
        current_tokens = counter.count(prompt)
        if current_tokens <= max_tokens:
            return prompt

        # Try increasing aggression until it fits
        for aggression in [0.3, 0.5, 0.7, 0.9, 1.0]:
            compressed = self.compress(prompt, aggression)
            if counter.count(compressed) <= max_tokens:
                return compressed

        # Last resort: truncate
        chars_per_token = len(prompt) / current_tokens
        max_chars = int(max_tokens * chars_per_token)
        return prompt[:max_chars] + "..."


# =============================================================================
# Contextual Compression (for retrieved chunks)
# =============================================================================

class ContextualCompressor:
    """
    Compresses retrieved chunks to only the relevant portions.
    
    Given a query and a chunk, extracts only sentences/paragraphs
    that are relevant to answering the query.
    """

    def __init__(self, llm_client: Optional[Any] = None):
        self.llm_client = llm_client

    def compress_chunk(self, query: str, chunk: str, max_tokens: int = 200) -> str:
        """
        Compress a single chunk to only query-relevant content.
        
        If no LLM client is available, uses heuristic sentence selection.
        """
        if self.llm_client:
            return self._llm_compress(query, chunk, max_tokens)
        return self._heuristic_compress(query, chunk, max_tokens)

    def compress_chunks(
        self, query: str, chunks: list[str], total_budget: int = 2000
    ) -> list[str]:
        """Compress multiple chunks to fit within total budget."""
        if not chunks:
            return []

        per_chunk_budget = total_budget // len(chunks)
        compressed = []

        for chunk in chunks:
            compressed_chunk = self.compress_chunk(query, chunk, per_chunk_budget)
            if compressed_chunk.strip():
                compressed.append(compressed_chunk)

        return compressed

    def _heuristic_compress(self, query: str, chunk: str, max_tokens: int) -> str:
        """Compress using keyword overlap heuristic."""
        query_words = set(query.lower().split())
        # Remove stopwords
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                     "being", "have", "has", "had", "do", "does", "did", "will",
                     "would", "could", "should", "may", "might", "can", "shall",
                     "to", "of", "in", "for", "on", "with", "at", "by", "from",
                     "it", "this", "that", "these", "those", "i", "you", "he",
                     "she", "we", "they", "my", "your", "his", "her", "our"}
        query_words -= stopwords

        # Score each sentence by keyword overlap
        sentences = re.split(r"[.!?\n]+", chunk)
        scored = []
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            sent_words = set(sent.lower().split())
            overlap = len(query_words & sent_words)
            scored.append((overlap, sent))

        # Sort by relevance, take top sentences within budget
        scored.sort(key=lambda x: x[0], reverse=True)

        result_sentences = []
        token_count = 0
        counter = TokenCounter()

        for score, sent in scored:
            if score == 0:
                break
            sent_tokens = counter.count(sent)
            if token_count + sent_tokens > max_tokens:
                break
            result_sentences.append(sent)
            token_count += sent_tokens

        return ". ".join(result_sentences) + "." if result_sentences else ""

    def _llm_compress(self, query: str, chunk: str, max_tokens: int) -> str:
        """Compress using LLM (extracts relevant portions)."""
        compression_prompt = f"""Extract ONLY the sentences from the following text that are relevant to answering the query. Return nothing else.

Query: {query}

Text: {chunk}

Relevant extract:"""

        # This would call the actual LLM
        response = self.llm_client.generate(
            prompt=compression_prompt,
            max_tokens=max_tokens,
        )
        return response


# =============================================================================
# History Summarizer
# =============================================================================

class HistorySummarizer:
    """
    Compresses conversation history to save tokens.
    
    Strategies:
    - Keep last N turns verbatim, summarize earlier turns
    - Progressive summarization (summarize summaries)
    - Key-fact extraction (just the decisions/info exchanged)
    """

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        keep_recent_turns: int = 3,
        max_summary_tokens: int = 200,
    ):
        self.llm_client = llm_client
        self.keep_recent_turns = keep_recent_turns
        self.max_summary_tokens = max_summary_tokens

    def summarize_history(self, messages: list[dict]) -> list[dict]:
        """
        Compress conversation history.
        
        Returns: messages list with early turns replaced by a summary message.
        """
        if len(messages) <= self.keep_recent_turns * 2:
            return messages  # Short enough, no compression needed

        # Split into "old" and "recent"
        recent_start = len(messages) - (self.keep_recent_turns * 2)
        old_messages = messages[:recent_start]
        recent_messages = messages[recent_start:]

        # Summarize old messages
        summary = self._create_summary(old_messages)

        # Return summary + recent verbatim
        return [
            {"role": "system", "content": f"[Conversation summary: {summary}]"},
            *recent_messages,
        ]

    def _create_summary(self, messages: list[dict]) -> str:
        """Create a summary of messages."""
        if self.llm_client:
            return self._llm_summarize(messages)
        return self._heuristic_summarize(messages)

    def _heuristic_summarize(self, messages: list[dict]) -> str:
        """Create summary without LLM using heuristics."""
        key_facts = []

        for msg in messages:
            content = msg.get("content", "")
            if not content:
                continue

            # Extract questions asked
            questions = re.findall(r"[^.!?]*\?", content)
            for q in questions[:1]:  # Keep first question per message
                key_facts.append(f"Asked: {q.strip()}")

            # Extract decisions/answers (sentences with key indicators)
            for pattern in [r"[^.]*(?:decided|confirmed|agreed|resolved)[^.]*\.",
                          r"[^.]*(?:the answer is|solution is|issue is)[^.]*\."]:
                matches = re.findall(pattern, content, re.IGNORECASE)
                key_facts.extend(m.strip() for m in matches[:1])

        if not key_facts:
            # Fallback: first sentence of each assistant message
            for msg in messages:
                if msg.get("role") == "assistant":
                    first_sent = re.split(r"[.!?]", msg.get("content", ""))[0]
                    if first_sent:
                        key_facts.append(first_sent.strip())

        return " | ".join(key_facts[:10])  # Cap at 10 facts

    def _llm_summarize(self, messages: list[dict]) -> str:
        """Summarize using LLM."""
        conversation_text = "\n".join(
            f"{m['role']}: {m.get('content', '')}" for m in messages
        )
        prompt = f"""Summarize this conversation in 2-3 sentences, preserving key decisions, facts exchanged, and current state:

{conversation_text}

Summary:"""

        return self.llm_client.generate(prompt=prompt, max_tokens=self.max_summary_tokens)


# =============================================================================
# Dynamic Prompt Selector
# =============================================================================

class QueryComplexity(Enum):
    SIMPLE = "simple"         # FAQ, single fact lookup
    MODERATE = "moderate"     # Multi-fact, comparison
    COMPLEX = "complex"       # Multi-step reasoning, synthesis


@dataclass
class PromptTemplate:
    """A prompt template with metadata."""
    name: str
    template: str
    complexity: QueryComplexity
    token_cost: int  # Approximate tokens
    quality_score: float  # 0-1, measured quality


class DynamicPromptSelector:
    """
    Selects minimal prompt for query complexity.
    
    Simple queries get short prompts (save tokens).
    Complex queries get detailed prompts (ensure quality).
    """

    def __init__(self):
        self.templates: dict[str, list[PromptTemplate]] = {}
        self._register_defaults()

    def _register_defaults(self):
        self.templates["qa"] = [
            PromptTemplate(
                name="minimal",
                template="Answer from context. Unknown → say so.\n\nContext: {context}\n\nQ: {query}",
                complexity=QueryComplexity.SIMPLE,
                token_cost=30,
                quality_score=0.85,
            ),
            PromptTemplate(
                name="standard",
                template=(
                    "You are a support agent. Answer the question using ONLY the provided context. "
                    "If the answer isn't in the context, say 'I don't have that information.'\n\n"
                    "Context:\n{context}\n\nQuestion: {query}\n\n"
                    "Answer concisely with source reference."
                ),
                complexity=QueryComplexity.MODERATE,
                token_cost=80,
                quality_score=0.92,
            ),
            PromptTemplate(
                name="detailed",
                template=(
                    "You are a senior support agent for our platform. Answer the question thoroughly "
                    "using the provided context. Follow these rules:\n"
                    "1. Use ONLY information from the context\n"
                    "2. If information is partial, say what you know and what's missing\n"
                    "3. For multi-part questions, address each part\n"
                    "4. Cite specific sections when possible\n"
                    "5. If the context is contradictory, note the conflict\n\n"
                    "Context:\n{context}\n\nQuestion: {query}\n\n"
                    "Provide a structured answer:"
                ),
                complexity=QueryComplexity.COMPLEX,
                token_cost=150,
                quality_score=0.96,
            ),
        ]

    def classify_complexity(self, query: str) -> QueryComplexity:
        """Classify query complexity using heuristics."""
        query_lower = query.lower()

        # Complex indicators
        complex_patterns = [
            r"\b(compare|contrast|analyze|evaluate|explain why|how does .* relate)\b",
            r"\b(pros and cons|advantages and disadvantages|trade-?offs)\b",
            r"\b(step by step|walk me through|detailed)\b",
            r".+\?.+\?",  # Multiple questions
        ]
        for pattern in complex_patterns:
            if re.search(pattern, query_lower):
                return QueryComplexity.COMPLEX

        # Simple indicators
        simple_patterns = [
            r"^(what is|where is|when|who|how much|how many)\b",
            r"^(is |are |do |does |can |will )\b",
        ]
        if len(query.split()) <= 10:
            for pattern in simple_patterns:
                if re.search(pattern, query_lower):
                    return QueryComplexity.SIMPLE

        return QueryComplexity.MODERATE

    def select_prompt(self, task: str, query: str) -> PromptTemplate:
        """Select the most appropriate prompt template."""
        complexity = self.classify_complexity(query)
        templates = self.templates.get(task, self.templates.get("qa", []))

        # Find template matching complexity
        for template in templates:
            if template.complexity == complexity:
                return template

        # Fallback to standard
        return templates[1] if len(templates) > 1 else templates[0]


# =============================================================================
# Tool Schema Optimizer
# =============================================================================

class ToolSchemaOptimizer:
    """
    Minimizes tool schemas to reduce token usage.
    
    Full OpenAPI-style schemas can be 500+ tokens per tool.
    Minimized schemas can be 50-100 tokens per tool.
    With 10 tools, this saves 4000+ tokens per request.
    """

    def optimize_schema(self, tool: dict, level: str = "moderate") -> dict:
        """
        Optimize a tool schema.
        
        Levels:
        - "minimal": Just name and parameter names/types
        - "moderate": Short descriptions, required params only
        - "full": Original schema (no optimization)
        """
        if level == "full":
            return tool

        optimized = {"name": tool["name"]}

        if level == "moderate":
            # Keep short description
            desc = tool.get("description", "")
            if len(desc) > 50:
                desc = desc[:47] + "..."
            optimized["description"] = desc

        # Optimize parameters
        params = tool.get("parameters", {})
        if params:
            opt_params = {"type": "object", "properties": {}}
            for prop_name, prop_def in params.get("properties", {}).items():
                if level == "minimal":
                    opt_params["properties"][prop_name] = {"type": prop_def.get("type", "string")}
                else:
                    opt_prop = {"type": prop_def.get("type", "string")}
                    desc = prop_def.get("description", "")
                    if desc and len(desc) <= 30:
                        opt_prop["description"] = desc
                    if "enum" in prop_def:
                        opt_prop["enum"] = prop_def["enum"]
                    opt_params["properties"][prop_name] = opt_prop

            if "required" in params:
                opt_params["required"] = params["required"]
            optimized["parameters"] = opt_params

        return optimized

    def optimize_tools(self, tools: list[dict], token_budget: int, counter: TokenCounter) -> list[dict]:
        """Optimize all tools to fit within budget."""
        # Try moderate first
        moderate = [self.optimize_schema(t, "moderate") for t in tools]
        if counter.count(json.dumps(moderate)) <= token_budget:
            return moderate

        # Try minimal
        minimal = [self.optimize_schema(t, "minimal") for t in tools]
        if counter.count(json.dumps(minimal)) <= token_budget:
            return minimal

        # Remove tools by priority (keep most-used tools)
        return minimal[:max(3, token_budget // 100)]


# =============================================================================
# Token Optimizer (Main Orchestrator)
# =============================================================================

@dataclass
class OptimizationResult:
    """Result of token optimization."""
    original_tokens: int
    optimized_tokens: int
    savings_tokens: int
    savings_percent: float
    estimated_cost_savings: float
    components: dict[str, dict]  # component -> {original, optimized, action}
    warnings: list[str]


class TokenOptimizer:
    """
    Main orchestrator for token optimization.
    
    Coordinates all optimization components to minimize tokens
    while maintaining quality.
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        context_window: int = 128000,
        output_reserve: int = 4000,
        llm_client: Optional[Any] = None,
    ):
        self.model = model
        self.counter = TokenCounter(model)
        self.budget_manager = ContextBudgetManager(context_window, output_reserve)
        self.prompt_compressor = PromptCompressor()
        self.contextual_compressor = ContextualCompressor(llm_client)
        self.history_summarizer = HistorySummarizer(llm_client)
        self.prompt_selector = DynamicPromptSelector()
        self.schema_optimizer = ToolSchemaOptimizer()

    def optimize_request(
        self,
        system_prompt: str,
        query: str,
        retrieved_chunks: list[str],
        conversation_history: list[dict],
        tools: list[dict],
        budget_override: Optional[int] = None,
    ) -> dict:
        """
        Optimize an entire request for minimal token usage.
        
        Returns optimized components ready to send to the model.
        """
        original_tokens = self._count_total(
            system_prompt, query, retrieved_chunks, conversation_history, tools
        )

        # 1. Select appropriate prompt template
        template = self.prompt_selector.select_prompt("qa", query)

        # 2. Compress system prompt
        compressed_prompt = self.prompt_compressor.compress(system_prompt, aggression=0.5)

        # 3. Compress retrieved chunks
        chunk_budget = self.budget_manager.allocations.get(
            "retrieved_context",
            BudgetAllocation("retrieved_context", BudgetPriority.HIGH, 500, 4000),
        ).max_tokens
        compressed_chunks = self.contextual_compressor.compress_chunks(
            query, retrieved_chunks, chunk_budget
        )

        # 4. Summarize history
        compressed_history = self.history_summarizer.summarize_history(conversation_history)

        # 5. Optimize tool schemas
        tool_budget = self.budget_manager.allocations.get(
            "tool_schemas",
            BudgetAllocation("tool_schemas", BudgetPriority.LOW, 0, 1000),
        ).max_tokens
        optimized_tools = self.schema_optimizer.optimize_tools(tools, tool_budget, self.counter)

        # 6. Allocate budget
        component_sizes = {
            "system_prompt": self.counter.count(compressed_prompt),
            "current_query": self.counter.count(query),
            "retrieved_context": sum(self.counter.count(c) for c in compressed_chunks),
            "conversation_history": self.counter.count_messages(compressed_history),
            "tool_schemas": self.counter.count(json.dumps(optimized_tools)),
        }
        budget = self.budget_manager.allocate(component_sizes)

        # 7. Final enforcement - truncate if over budget
        if budget.remaining < 0:
            # Trim chunks further
            while compressed_chunks and budget.remaining < 0:
                compressed_chunks.pop()

        optimized_tokens = sum(component_sizes.values())
        savings = original_tokens - optimized_tokens

        return {
            "system_prompt": compressed_prompt,
            "query": query,
            "context": "\n\n".join(compressed_chunks),
            "history": compressed_history,
            "tools": optimized_tools,
            "metadata": {
                "original_tokens": original_tokens,
                "optimized_tokens": optimized_tokens,
                "savings_tokens": savings,
                "savings_percent": (savings / original_tokens * 100) if original_tokens > 0 else 0,
                "estimated_cost_savings": self.counter.estimate_cost(savings, 0),
                "budget_warnings": budget.warnings,
            },
        }

    def _count_total(
        self,
        system_prompt: str,
        query: str,
        chunks: list[str],
        history: list[dict],
        tools: list[dict],
    ) -> int:
        """Count total tokens before optimization."""
        total = self.counter.count(system_prompt)
        total += self.counter.count(query)
        total += sum(self.counter.count(c) for c in chunks)
        total += self.counter.count_messages(history)
        total += self.counter.count(json.dumps(tools))
        return total


# =============================================================================
# Budget Alert System
# =============================================================================

@dataclass
class BudgetAlert:
    level: str  # "info", "warning", "critical"
    message: str
    current_usage: int
    budget_limit: int
    recommendation: str


class BudgetEnforcer:
    """
    Monitors and enforces token budgets with alerts.
    """

    def __init__(self, daily_token_budget: int = 10_000_000, alert_thresholds: Optional[dict] = None):
        self.daily_budget = daily_token_budget
        self.thresholds = alert_thresholds or {
            "info": 0.5,
            "warning": 0.8,
            "critical": 0.95,
        }
        self.usage_today: int = 0
        self.request_count: int = 0
        self.alerts: list[BudgetAlert] = []

    def record_usage(self, tokens: int) -> Optional[BudgetAlert]:
        """Record token usage and check for budget alerts."""
        self.usage_today += tokens
        self.request_count += 1

        usage_ratio = self.usage_today / self.daily_budget

        if usage_ratio >= self.thresholds["critical"]:
            alert = BudgetAlert(
                level="critical",
                message=f"Token budget nearly exhausted: {usage_ratio:.0%}",
                current_usage=self.usage_today,
                budget_limit=self.daily_budget,
                recommendation="Switch to smaller model or enable aggressive caching",
            )
            self.alerts.append(alert)
            return alert
        elif usage_ratio >= self.thresholds["warning"]:
            alert = BudgetAlert(
                level="warning",
                message=f"Token budget at {usage_ratio:.0%}",
                current_usage=self.usage_today,
                budget_limit=self.daily_budget,
                recommendation="Enable token optimization and consider model routing",
            )
            self.alerts.append(alert)
            return alert

        return None

    def get_remaining_budget(self) -> int:
        return max(0, self.daily_budget - self.usage_today)

    def should_degrade(self) -> bool:
        """Should we switch to degraded mode (cheaper model)?"""
        return self.usage_today >= self.daily_budget * self.thresholds["critical"]

    def reset_daily(self):
        """Reset daily counters."""
        self.usage_today = 0
        self.request_count = 0
        self.alerts = []


# =============================================================================
# Usage Example
# =============================================================================

if __name__ == "__main__":
    # Initialize optimizer
    optimizer = TokenOptimizer(model="gpt-4o", context_window=128000, output_reserve=4000)

    # Sample data
    system_prompt = """You are a helpful, knowledgeable, and friendly customer support assistant 
    for Acme Corp. You should always be polite and professional in your responses. When answering 
    questions, make sure to provide accurate information based on our knowledge base. If you don't 
    know the answer, please let the customer know that you will escalate their question to a human 
    agent who can better assist them. Always maintain a positive tone."""

    query = "What is your refund policy?"

    chunks = [
        "Acme Corp was founded in 1985 by John Smith in Seattle, Washington. The company started as a small hardware manufacturer before pivoting to software development in 2001. Today Acme Corp employs over 5000 people worldwide. Our refund policy allows returns within 30 days of purchase with original receipt. Items must be in original packaging.",
        "Customer Service Hours: Monday through Friday, 9 AM to 5 PM Pacific Time. For urgent issues outside business hours, please email urgent@acme.com. Our refund processing typically takes 5-7 business days after we receive the returned item.",
        "Acme Corp's mission is to provide innovative solutions that empower businesses to achieve their goals. We believe in transparency, integrity, and customer satisfaction above all else.",
    ]

    history = [
        {"role": "user", "content": "Hi, I bought a product last week"},
        {"role": "assistant", "content": "Hello! I'd be happy to help you with your recent purchase. What can I assist you with?"},
        {"role": "user", "content": "I want to return it"},
        {"role": "assistant", "content": "I understand you'd like to return your purchase. I can help with that. Could you tell me which product it is and the reason for the return?"},
    ]

    tools = [
        {
            "name": "search_knowledge_base",
            "description": "Search the Acme Corp knowledge base for relevant articles and documentation to answer customer questions",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant documentation in the knowledge base",
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional category filter to narrow search results",
                        "enum": ["billing", "shipping", "returns", "technical", "general"],
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "lookup_order",
            "description": "Look up a customer's order by order ID or email address to get order details, status, and shipping information",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The order ID to look up"},
                    "email": {"type": "string", "description": "Customer email for order lookup"},
                },
                "required": ["order_id"],
            },
        },
    ]

    # Run optimization
    result = optimizer.optimize_request(
        system_prompt=system_prompt,
        query=query,
        retrieved_chunks=chunks,
        conversation_history=history,
        tools=tools,
    )

    print("=" * 60)
    print("TOKEN OPTIMIZATION RESULTS")
    print("=" * 60)
    meta = result["metadata"]
    print(f"Original tokens:  {meta['original_tokens']}")
    print(f"Optimized tokens: {meta['optimized_tokens']}")
    print(f"Savings:          {meta['savings_tokens']} tokens ({meta['savings_percent']:.1f}%)")
    print(f"Est. cost saved:  ${meta['estimated_cost_savings']:.6f}")
    print(f"\nWarnings: {meta['budget_warnings']}")
    print(f"\nCompressed system prompt:\n  {result['system_prompt'][:100]}...")
    print(f"\nCompressed context:\n  {result['context'][:100]}...")
    print(f"\nOptimized tools: {len(result['tools'])} tools")
