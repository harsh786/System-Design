"""
Query Decomposition Engine for Agentic RAG

Handles: simple query detection, multi-hop detection, sub-question generation,
dependency graph construction, parallel/sequential execution, answer synthesis,
and confidence aggregation.
"""

import asyncio
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ─────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────

class QueryComplexity(Enum):
    SIMPLE = "simple"              # Direct lookup, no decomposition
    MULTI_ENTITY = "multi_entity"  # Multiple entities, parallel retrieval
    MULTI_HOP = "multi_hop"        # Sequential reasoning chain
    COMPARATIVE = "comparative"    # Compare entities/concepts
    TEMPORAL = "temporal"          # Time-dependent reasoning
    CONDITIONAL = "conditional"    # If-then reasoning


class ExecutionMode(Enum):
    DIRECT = "direct"          # No decomposition, retrieve directly
    PARALLEL = "parallel"      # Sub-questions are independent
    SEQUENTIAL = "sequential"  # Sub-questions depend on each other
    MIXED = "mixed"            # Some parallel, some sequential


@dataclass
class SubQuestion:
    id: str
    text: str
    depends_on: list[str] = field(default_factory=list)
    tool_hint: str = "vector_search"
    priority: int = 0  # Higher = more important for final answer
    answer: Optional[str] = None
    confidence: float = 0.0
    evidence_chunks: list[dict] = field(default_factory=list)
    execution_tier: int = 0  # 0 = first to execute


@dataclass
class DecompositionResult:
    original_query: str
    complexity: QueryComplexity
    execution_mode: ExecutionMode
    sub_questions: list[SubQuestion]
    synthesis_strategy: str  # "concatenate", "compare", "chain", "aggregate"
    estimated_hops: int = 1


@dataclass
class SynthesizedAnswer:
    text: str
    confidence: float
    sub_answers: list[dict]  # {sub_question_id, answer, confidence}
    reasoning_chain: list[str]


# ─────────────────────────────────────────────────────────────
# Complexity Detector
# ─────────────────────────────────────────────────────────────

class ComplexityDetector:
    """Determines whether a query needs decomposition and what type."""
    
    # Heuristic indicators
    MULTI_HOP_INDICATORS = [
        "who is the", "what is the .* of the .* that",
        "after .* what", "before .* did",
        "the company that", "the person who",
        "as a result of", "because of",
    ]
    
    COMPARATIVE_INDICATORS = [
        "compare", "difference between", "vs", "versus",
        "better than", "worse than", "how does .* compare",
        "advantages and disadvantages", "pros and cons",
    ]
    
    TEMPORAL_INDICATORS = [
        "after", "before", "since", "until",
        "during", "when did", "how has .* changed",
        "trend", "over time", "historically",
    ]
    
    MULTI_ENTITY_INDICATORS = [
        " and ", " or ", "both", "each",
        "all of", "list of", "multiple",
    ]
    
    SYSTEM_PROMPT = """Analyze this query and determine its complexity for retrieval:

1. SIMPLE: Single fact, single entity, direct lookup. Example: "What is our return policy?"
2. MULTI_ENTITY: Multiple independent entities to look up. Example: "What are the prices of Product A and Product B?"
3. MULTI_HOP: Answer requires chaining facts. Example: "What school did the CEO of Apple attend?"
4. COMPARATIVE: Comparing two or more things. Example: "How does Redis compare to Memcached for our use case?"
5. TEMPORAL: Time-dependent reasoning. Example: "How has our churn rate changed since the price increase?"
6. CONDITIONAL: If-then or scenario-based. Example: "If we migrate to AWS, what compliance certs do we need?"

Also determine:
- needs_decomposition: true/false
- estimated_hops: number of retrieval steps needed
- execution_mode: "direct", "parallel", "sequential", "mixed"

Respond in JSON:
{
  "complexity": "simple|multi_entity|multi_hop|comparative|temporal|conditional",
  "needs_decomposition": true/false,
  "estimated_hops": 1-5,
  "execution_mode": "direct|parallel|sequential|mixed",
  "reasoning": "brief explanation"
}"""
    
    def __init__(self, llm):
        self.llm = llm
    
    async def detect(self, query: str) -> tuple[QueryComplexity, bool, ExecutionMode, int]:
        """
        Returns: (complexity, needs_decomposition, execution_mode, estimated_hops)
        """
        # Quick heuristic pre-check for obviously simple queries
        if self._is_obviously_simple(query):
            return QueryComplexity.SIMPLE, False, ExecutionMode.DIRECT, 1
        
        # Use LLM for nuanced classification
        result = await self.llm.generate_json(
            f"Query: {query}",
            system=self.SYSTEM_PROMPT
        )
        
        complexity = QueryComplexity(result.get("complexity", "simple"))
        needs_decomp = result.get("needs_decomposition", False)
        exec_mode = ExecutionMode(result.get("execution_mode", "direct"))
        hops = result.get("estimated_hops", 1)
        
        return complexity, needs_decomp, exec_mode, hops
    
    def _is_obviously_simple(self, query: str) -> bool:
        """Fast heuristic check for simple queries."""
        # Short queries with no complexity indicators
        words = query.split()
        if len(words) <= 8:
            query_lower = query.lower()
            has_complexity = any(
                indicator in query_lower
                for indicators in [
                    self.MULTI_HOP_INDICATORS,
                    self.COMPARATIVE_INDICATORS,
                    self.TEMPORAL_INDICATORS,
                ]
                for indicator in indicators
            )
            if not has_complexity:
                return True
        return False


# ─────────────────────────────────────────────────────────────
# Sub-Question Generator
# ─────────────────────────────────────────────────────────────

class SubQuestionGenerator:
    """Generates sub-questions from a complex query using LLM."""
    
    SYSTEM_PROMPT = """You are a query decomposition expert. Break this complex question into
atomic sub-questions that can each be answered with a single retrieval operation.

Rules:
1. Each sub-question should target ONE specific fact or piece of information
2. Specify dependencies: if sub-question B needs the answer to A, mark it
3. Suggest the best retrieval tool:
   - "vector_search": conceptual, how/why questions
   - "sql_query": numeric, aggregation, exact facts from structured data
   - "graph_search": entity relationships
   - "api_call": real-time data
   - "web_search": recent events, external knowledge
4. Assign priority (1-5, higher = more critical for final answer)
5. Keep sub-questions minimal — don't over-decompose simple aspects

For dependency references, use the sub-question ID in brackets: [sq1], [sq2], etc.
If a sub-question needs the answer from sq1, write it as: "What is the revenue of [sq1.answer]?"

Respond in JSON:
{
  "sub_questions": [
    {
      "id": "sq1",
      "text": "Who is the current CEO?",
      "depends_on": [],
      "tool_hint": "vector_search",
      "priority": 3
    },
    {
      "id": "sq2",
      "text": "What is the revenue of [sq1.answer]'s company?",
      "depends_on": ["sq1"],
      "tool_hint": "sql_query",
      "priority": 5
    }
  ],
  "synthesis_strategy": "chain"
}

Synthesis strategies:
- "concatenate": Combine all sub-answers into a comprehensive response
- "compare": Structure as a comparison (for comparative queries)
- "chain": Final answer comes from last sub-question in the chain
- "aggregate": Summarize/aggregate multiple sub-answers"""
    
    def __init__(self, llm):
        self.llm = llm
    
    async def generate(self, query: str, complexity: QueryComplexity, context: Optional[str] = None) -> tuple[list[SubQuestion], str]:
        """
        Generate sub-questions for a complex query.
        Returns: (sub_questions, synthesis_strategy)
        """
        prompt = f"Complex question: {query}\nComplexity type: {complexity.value}"
        if context:
            prompt += f"\nConversation context: {context}"
        
        result = await self.llm.generate_json(prompt, system=self.SYSTEM_PROMPT)
        
        sub_questions = []
        for sq_data in result.get("sub_questions", []):
            sub_questions.append(SubQuestion(
                id=sq_data["id"],
                text=sq_data["text"],
                depends_on=sq_data.get("depends_on", []),
                tool_hint=sq_data.get("tool_hint", "vector_search"),
                priority=sq_data.get("priority", 1),
            ))
        
        synthesis_strategy = result.get("synthesis_strategy", "concatenate")
        
        # Assign execution tiers
        sub_questions = self._assign_tiers(sub_questions)
        
        return sub_questions, synthesis_strategy
    
    def _assign_tiers(self, sub_questions: list[SubQuestion]) -> list[SubQuestion]:
        """Assign execution tiers based on dependency graph (topological sort)."""
        assigned = {}  # id → tier
        
        def get_tier(sq_id: str, visited: set) -> int:
            if sq_id in assigned:
                return assigned[sq_id]
            if sq_id in visited:
                return 0  # Circular dep, break cycle
            
            visited.add(sq_id)
            sq = next((s for s in sub_questions if s.id == sq_id), None)
            if not sq or not sq.depends_on:
                assigned[sq_id] = 0
                return 0
            
            max_dep_tier = max(get_tier(dep, visited) for dep in sq.depends_on)
            tier = max_dep_tier + 1
            assigned[sq_id] = tier
            return tier
        
        for sq in sub_questions:
            sq.execution_tier = get_tier(sq.id, set())
        
        return sub_questions


# ─────────────────────────────────────────────────────────────
# Dependency Graph Manager
# ─────────────────────────────────────────────────────────────

class DependencyGraph:
    """Manages the dependency DAG between sub-questions."""
    
    def __init__(self, sub_questions: list[SubQuestion]):
        self.sub_questions = {sq.id: sq for sq in sub_questions}
        self.adjacency: dict[str, list[str]] = {}  # id → list of dependents
        self._build_graph()
    
    def _build_graph(self):
        """Build adjacency list from dependencies."""
        for sq in self.sub_questions.values():
            for dep in sq.depends_on:
                if dep not in self.adjacency:
                    self.adjacency[dep] = []
                self.adjacency[dep].append(sq.id)
    
    def get_execution_order(self) -> list[list[str]]:
        """
        Returns execution tiers: list of lists where each inner list
        contains sub-question IDs that can execute in parallel.
        """
        tiers: dict[int, list[str]] = {}
        for sq in self.sub_questions.values():
            tier = sq.execution_tier
            if tier not in tiers:
                tiers[tier] = []
            tiers[tier].append(sq.id)
        
        return [tiers[t] for t in sorted(tiers.keys())]
    
    def get_ready_questions(self, completed: set[str]) -> list[str]:
        """Get sub-questions whose dependencies are all completed."""
        ready = []
        for sq_id, sq in self.sub_questions.items():
            if sq_id not in completed:
                if all(dep in completed for dep in sq.depends_on):
                    ready.append(sq_id)
        return ready
    
    def resolve_references(self, sq_id: str) -> str:
        """Resolve [sq1.answer] references in a sub-question's text."""
        sq = self.sub_questions[sq_id]
        resolved = sq.text
        
        for dep_id in sq.depends_on:
            dep = self.sub_questions.get(dep_id)
            if dep and dep.answer:
                resolved = resolved.replace(f"[{dep_id}.answer]", dep.answer)
                resolved = resolved.replace(f"[{dep_id}]", dep.answer)
        
        return resolved
    
    def has_circular_dependencies(self) -> bool:
        """Check for circular dependencies using DFS."""
        WHITE, GRAY, BLACK = 0, 1, 2
        colors = {sq_id: WHITE for sq_id in self.sub_questions}
        
        def dfs(node: str) -> bool:
            colors[node] = GRAY
            sq = self.sub_questions[node]
            for dep in sq.depends_on:
                if dep not in colors:
                    continue
                if colors[dep] == GRAY:
                    return True  # Back edge = cycle
                if colors[dep] == WHITE and dfs(dep):
                    return True
            colors[node] = BLACK
            return False
        
        return any(dfs(sq_id) for sq_id, color in colors.items() if color == WHITE)


# ─────────────────────────────────────────────────────────────
# Parallel/Sequential Executor
# ─────────────────────────────────────────────────────────────

class SubQuestionExecutor:
    """Executes sub-questions respecting dependency ordering."""
    
    def __init__(self, retrieval_fn, answer_fn):
        """
        Args:
            retrieval_fn: async (query, tool_hint) -> list[chunks]
            answer_fn: async (question, evidence) -> str
        """
        self.retrieve = retrieval_fn
        self.answer = answer_fn
    
    async def execute_all(self, sub_questions: list[SubQuestion]) -> list[SubQuestion]:
        """Execute all sub-questions respecting dependencies."""
        graph = DependencyGraph(sub_questions)
        
        if graph.has_circular_dependencies():
            raise ValueError("Circular dependencies detected in sub-questions")
        
        execution_order = graph.get_execution_order()
        completed: set[str] = set()
        
        for tier_ids in execution_order:
            # Execute all questions in this tier in parallel
            tasks = []
            for sq_id in tier_ids:
                resolved_query = graph.resolve_references(sq_id)
                sq = graph.sub_questions[sq_id]
                tasks.append(self._execute_one(sq, resolved_query))
            
            await asyncio.gather(*tasks)
            completed.update(tier_ids)
        
        return list(graph.sub_questions.values())
    
    async def _execute_one(self, sq: SubQuestion, resolved_query: str) -> None:
        """Execute a single sub-question: retrieve + answer."""
        # Retrieve evidence
        chunks = await self.retrieve(resolved_query, sq.tool_hint)
        sq.evidence_chunks = chunks
        
        # Generate sub-answer
        if chunks:
            sq.answer = await self.answer(resolved_query, chunks)
            # Confidence from retrieval scores
            scores = [c.get("score", 0.5) for c in chunks[:3]]
            sq.confidence = sum(scores) / len(scores) if scores else 0.0
        else:
            sq.answer = None
            sq.confidence = 0.0


# ─────────────────────────────────────────────────────────────
# Answer Synthesizer
# ─────────────────────────────────────────────────────────────

class AnswerSynthesizer:
    """Synthesizes final answer from multiple sub-question answers."""
    
    SYNTHESIS_PROMPTS = {
        "concatenate": """Combine these sub-answers into a comprehensive, coherent response.
Ensure smooth transitions and no repetition.

Question: {question}
Sub-answers:
{sub_answers}

Provide a unified answer:""",
        
        "compare": """Create a structured comparison based on these sub-answers.

Question: {question}
Sub-answers:
{sub_answers}

Provide a clear comparison highlighting similarities and differences:""",
        
        "chain": """The following sub-answers form a reasoning chain. Use them to answer the original question.
The final sub-answer is most directly relevant, but earlier ones provide supporting context.

Question: {question}
Reasoning chain:
{sub_answers}

Provide the final answer based on this chain of reasoning:""",
        
        "aggregate": """Summarize and aggregate these sub-answers into a concise response.

Question: {question}
Sub-answers:
{sub_answers}

Provide an aggregated summary:""",
    }
    
    def __init__(self, llm):
        self.llm = llm
    
    async def synthesize(
        self,
        original_query: str,
        sub_questions: list[SubQuestion],
        strategy: str = "concatenate",
    ) -> SynthesizedAnswer:
        """Synthesize final answer from sub-question answers."""
        
        # Format sub-answers
        sub_answers_text = ""
        sub_answer_records = []
        
        for sq in sorted(sub_questions, key=lambda s: s.execution_tier):
            if sq.answer:
                sub_answers_text += f"\n[{sq.id}] Q: {sq.text}\n    A: {sq.answer}\n"
                sub_answer_records.append({
                    "sub_question_id": sq.id,
                    "answer": sq.answer,
                    "confidence": sq.confidence,
                })
        
        # Select synthesis prompt
        prompt_template = self.SYNTHESIS_PROMPTS.get(strategy, self.SYNTHESIS_PROMPTS["concatenate"])
        prompt = prompt_template.format(
            question=original_query,
            sub_answers=sub_answers_text,
        )
        
        # Generate synthesized answer
        answer_text = await self.llm.generate(prompt)
        
        # Aggregate confidence
        confidences = [sq.confidence for sq in sub_questions if sq.answer]
        aggregate_confidence = self._aggregate_confidence(confidences, strategy)
        
        # Build reasoning chain
        reasoning_chain = [
            f"Step {i+1}: {sq.text} → {sq.answer}"
            for i, sq in enumerate(sorted(sub_questions, key=lambda s: s.execution_tier))
            if sq.answer
        ]
        
        return SynthesizedAnswer(
            text=answer_text,
            confidence=aggregate_confidence,
            sub_answers=sub_answer_records,
            reasoning_chain=reasoning_chain,
        )
    
    def _aggregate_confidence(self, confidences: list[float], strategy: str) -> float:
        """Aggregate confidence scores based on synthesis strategy."""
        if not confidences:
            return 0.0
        
        if strategy == "chain":
            # Chain: confidence is product (weakest link matters)
            result = 1.0
            for c in confidences:
                result *= c
            return result
        
        elif strategy == "compare":
            # Compare: minimum confidence (need both sides)
            return min(confidences)
        
        elif strategy == "aggregate":
            # Aggregate: average
            return sum(confidences) / len(confidences)
        
        else:  # concatenate
            # Weighted average by priority would be ideal; use simple average
            return sum(confidences) / len(confidences)


# ─────────────────────────────────────────────────────────────
# Complete Decomposition Pipeline
# ─────────────────────────────────────────────────────────────

class QueryDecompositionPipeline:
    """
    End-to-end pipeline: detect complexity → decompose → execute → synthesize.
    """
    
    def __init__(self, llm, retrieval_fn, answer_fn):
        self.llm = llm
        self.complexity_detector = ComplexityDetector(llm)
        self.sub_question_generator = SubQuestionGenerator(llm)
        self.executor = SubQuestionExecutor(retrieval_fn, answer_fn)
        self.synthesizer = AnswerSynthesizer(llm)
    
    async def run(self, query: str, context: Optional[str] = None) -> DecompositionResult:
        """Run the full decomposition pipeline."""
        
        # Step 1: Detect complexity
        complexity, needs_decomp, exec_mode, hops = await self.complexity_detector.detect(query)
        
        if not needs_decomp:
            # Simple query — return as single sub-question
            return DecompositionResult(
                original_query=query,
                complexity=complexity,
                execution_mode=ExecutionMode.DIRECT,
                sub_questions=[SubQuestion(id="sq1", text=query, tool_hint="vector_search", priority=5)],
                synthesis_strategy="chain",
                estimated_hops=1,
            )
        
        # Step 2: Generate sub-questions
        sub_questions, synthesis_strategy = await self.sub_question_generator.generate(
            query, complexity, context
        )
        
        # Step 3: Execute sub-questions
        executed = await self.executor.execute_all(sub_questions)
        
        return DecompositionResult(
            original_query=query,
            complexity=complexity,
            execution_mode=exec_mode,
            sub_questions=executed,
            synthesis_strategy=synthesis_strategy,
            estimated_hops=hops,
        )
    
    async def run_and_synthesize(self, query: str, context: Optional[str] = None) -> SynthesizedAnswer:
        """Run pipeline and return synthesized answer."""
        decomp_result = await self.run(query, context)
        
        return await self.synthesizer.synthesize(
            original_query=query,
            sub_questions=decomp_result.sub_questions,
            strategy=decomp_result.synthesis_strategy,
        )


# ─────────────────────────────────────────────────────────────
# Example Usage
# ─────────────────────────────────────────────────────────────

async def example():
    """Demonstrate the query decomposition pipeline."""
    
    # Mock LLM and retrieval
    class MockLLM:
        async def generate(self, prompt, system="", temperature=0.0):
            return "Mock answer based on evidence."
        
        async def generate_json(self, prompt, system="", temperature=0.0):
            # Simulate decomposition for a complex query
            if "decompose" in system.lower() or "sub_questions" in system.lower():
                return {
                    "sub_questions": [
                        {"id": "sq1", "text": "What is our current churn rate?", "depends_on": [], "tool_hint": "sql_query", "priority": 4},
                        {"id": "sq2", "text": "When did we increase prices?", "depends_on": [], "tool_hint": "vector_search", "priority": 3},
                        {"id": "sq3", "text": "What was the churn rate before [sq2.answer]?", "depends_on": ["sq2"], "tool_hint": "sql_query", "priority": 4},
                        {"id": "sq4", "text": "Compare [sq1.answer] to [sq3.answer]", "depends_on": ["sq1", "sq3"], "tool_hint": "vector_search", "priority": 5},
                    ],
                    "synthesis_strategy": "chain",
                }
            elif "complexity" in system.lower():
                return {
                    "complexity": "temporal",
                    "needs_decomposition": True,
                    "estimated_hops": 3,
                    "execution_mode": "mixed",
                }
            return {}
    
    async def mock_retrieve(query, tool_hint):
        return [{"text": f"Evidence for: {query}", "score": 0.85}]
    
    async def mock_answer(question, evidence):
        return f"Answer to '{question}' based on {len(evidence)} chunks."
    
    llm = MockLLM()
    pipeline = QueryDecompositionPipeline(llm, mock_retrieve, mock_answer)
    
    # Run on a complex query
    query = "How has our churn rate changed since we increased prices?"
    result = await pipeline.run(query)
    
    print(f"Query: {query}")
    print(f"Complexity: {result.complexity.value}")
    print(f"Execution mode: {result.execution_mode.value}")
    print(f"Estimated hops: {result.estimated_hops}")
    print(f"\nSub-questions ({len(result.sub_questions)}):")
    for sq in result.sub_questions:
        print(f"  [{sq.id}] (tier {sq.execution_tier}) {sq.text}")
        print(f"       depends_on={sq.depends_on}, tool={sq.tool_hint}")
        if sq.answer:
            print(f"       answer: {sq.answer}")
    
    # Synthesize
    synth = await pipeline.synthesizer.synthesize(query, result.sub_questions, result.synthesis_strategy)
    print(f"\nSynthesized answer: {synth.text}")
    print(f"Confidence: {synth.confidence:.2f}")
    print(f"Reasoning chain: {synth.reasoning_chain}")


if __name__ == "__main__":
    asyncio.run(example())
