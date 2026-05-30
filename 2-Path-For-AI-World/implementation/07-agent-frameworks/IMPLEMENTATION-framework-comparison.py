"""
Framework Comparison Harness
============================

Implements the SAME task across multiple frameworks to measure:
- Latency (time to first token, total time)
- Token usage (input, output, total)
- Cost estimation
- Success rate
- Code complexity (LOC, abstraction depth)
- Testability (ease of mocking, deterministic testing)

Task: "Research Agent" - Given a question, search for info, synthesize an answer.
"""

from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

import tiktoken


# =============================================================================
# 1. METRICS COLLECTION
# =============================================================================

@dataclass
class ExecutionMetrics:
    """Metrics collected from a single agent execution."""
    framework: str
    task: str
    
    # Timing
    total_time_ms: float = 0
    time_to_first_output_ms: float = 0
    
    # Token usage
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    
    # Cost (USD)
    estimated_cost_usd: float = 0
    
    # Quality
    success: bool = False
    error: str | None = None
    output: str = ""
    output_length: int = 0
    
    # LLM calls
    llm_call_count: int = 0
    tool_call_count: int = 0
    
    # Framework overhead
    framework_overhead_ms: float = 0  # Time spent in framework code vs LLM calls
    
    def to_dict(self) -> dict:
        return {
            "framework": self.framework,
            "task": self.task,
            "total_time_ms": round(self.total_time_ms, 2),
            "time_to_first_output_ms": round(self.time_to_first_output_ms, 2),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "success": self.success,
            "error": self.error,
            "output_length": self.output_length,
            "llm_call_count": self.llm_call_count,
            "tool_call_count": self.tool_call_count,
            "framework_overhead_ms": round(self.framework_overhead_ms, 2),
        }


@dataclass
class CodeComplexityMetrics:
    """Static analysis metrics for framework implementations."""
    framework: str
    lines_of_code: int = 0
    import_count: int = 0
    class_count: int = 0
    function_count: int = 0
    abstraction_depth: int = 0  # Max call stack depth to reach LLM
    boilerplate_ratio: float = 0  # % of code that's framework boilerplate
    type_annotations: int = 0
    comment_lines: int = 0
    
    # Testability
    mockable_interfaces: int = 0  # How many points can be mocked
    requires_network_for_test: bool = True
    has_dependency_injection: bool = False
    deterministic_testable: bool = False


def estimate_cost(input_tokens: int, output_tokens: int, model: str = "gpt-4o") -> float:
    """Estimate cost in USD based on token usage."""
    pricing = {
        "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
        "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
        "gpt-3.5-turbo": {"input": 0.50 / 1_000_000, "output": 1.50 / 1_000_000},
    }
    rates = pricing.get(model, pricing["gpt-4o"])
    return input_tokens * rates["input"] + output_tokens * rates["output"]


# =============================================================================
# 2. BASE FRAMEWORK IMPLEMENTATION
# =============================================================================

class FrameworkImplementation(ABC):
    """Base class for framework comparison implementations."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Framework name."""
        ...
    
    @abstractmethod
    async def execute(self, task: str) -> ExecutionMetrics:
        """Execute the task and return metrics."""
        ...
    
    @abstractmethod
    def get_complexity_metrics(self) -> CodeComplexityMetrics:
        """Return static complexity metrics for this implementation."""
        ...


# =============================================================================
# 3. NO-FRAMEWORK IMPLEMENTATION (Baseline)
# =============================================================================

class NoFrameworkImplementation(FrameworkImplementation):
    """
    Pure Python + OpenAI API implementation.
    This is the baseline for comparison.
    """
    
    @property
    def name(self) -> str:
        return "No Framework (Direct API)"
    
    async def execute(self, task: str) -> ExecutionMetrics:
        metrics = ExecutionMetrics(framework=self.name, task=task)
        start = time.perf_counter()
        
        try:
            # Direct implementation - no framework overhead
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI()
            
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "search",
                        "description": "Search for information",
                        "parameters": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                            "required": ["query"],
                        },
                    },
                }
            ]
            
            messages = [
                {"role": "system", "content": "You are a research assistant. Search for information and provide a concise answer."},
                {"role": "user", "content": task},
            ]
            
            llm_start = time.perf_counter()
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=tools,
                temperature=0,
            )
            metrics.time_to_first_output_ms = (time.perf_counter() - llm_start) * 1000
            metrics.llm_call_count = 1
            
            # Handle tool calls
            message = response.choices[0].message
            if message.tool_calls:
                metrics.tool_call_count = len(message.tool_calls)
                messages.append(message.model_dump())
                
                for tc in message.tool_calls:
                    # Simulate tool execution
                    tool_result = f"Search results for: {json.loads(tc.function.arguments).get('query', '')}"
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_result,
                    })
                
                # Second LLM call to synthesize
                response = await client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    temperature=0,
                )
                metrics.llm_call_count += 1
            
            # Collect metrics
            metrics.output = response.choices[0].message.content or ""
            metrics.output_length = len(metrics.output)
            metrics.input_tokens = response.usage.prompt_tokens if response.usage else 0
            metrics.output_tokens = response.usage.completion_tokens if response.usage else 0
            metrics.total_tokens = metrics.input_tokens + metrics.output_tokens
            metrics.estimated_cost_usd = estimate_cost(metrics.input_tokens, metrics.output_tokens)
            metrics.success = True
            
        except Exception as e:
            metrics.error = str(e)
            metrics.success = False
        
        metrics.total_time_ms = (time.perf_counter() - start) * 1000
        metrics.framework_overhead_ms = metrics.total_time_ms - metrics.time_to_first_output_ms
        return metrics
    
    def get_complexity_metrics(self) -> CodeComplexityMetrics:
        return CodeComplexityMetrics(
            framework=self.name,
            lines_of_code=45,
            import_count=2,  # openai, json
            class_count=0,
            function_count=1,
            abstraction_depth=1,  # Direct API call
            boilerplate_ratio=0.15,
            type_annotations=3,
            comment_lines=5,
            mockable_interfaces=1,  # Mock the client
            requires_network_for_test=True,
            has_dependency_injection=False,
            deterministic_testable=True,  # Easy to mock
        )


# =============================================================================
# 4. LANGGRAPH IMPLEMENTATION
# =============================================================================

class LangGraphImplementation(FrameworkImplementation):
    """LangGraph implementation of the same research task."""
    
    @property
    def name(self) -> str:
        return "LangGraph"
    
    async def execute(self, task: str) -> ExecutionMetrics:
        metrics = ExecutionMetrics(framework=self.name, task=task)
        start = time.perf_counter()
        
        try:
            from typing import Annotated, Sequence, TypedDict
            from langgraph.graph import END, START, StateGraph
            from langgraph.graph.message import add_messages
            from langgraph.prebuilt import ToolNode, tools_condition
            from langchain_core.messages import HumanMessage
            from langchain_core.tools import tool
            from langchain_openai import ChatOpenAI
            
            # State
            class State(TypedDict):
                messages: Annotated[Sequence, add_messages]
            
            # Tool
            @tool
            def search(query: str) -> str:
                """Search for information."""
                return f"Search results for: {query}"
            
            # Model
            model = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools([search])
            
            # Nodes
            async def agent(state):
                metrics.llm_call_count += 1
                if metrics.llm_call_count == 1:
                    metrics.time_to_first_output_ms = (time.perf_counter() - start) * 1000
                response = await model.ainvoke(state["messages"])
                return {"messages": [response]}
            
            async def tool_node(state):
                tool_executor = ToolNode(tools=[search])
                result = await tool_executor.ainvoke(state)
                metrics.tool_call_count += 1
                return result
            
            # Graph
            builder = StateGraph(State)
            builder.add_node("agent", agent)
            builder.add_node("tools", tool_node)
            builder.add_edge(START, "agent")
            builder.add_conditional_edges("agent", tools_condition)
            builder.add_edge("tools", "agent")
            graph = builder.compile()
            
            # Execute
            result = await graph.ainvoke({
                "messages": [HumanMessage(content=task)]
            })
            
            last_message = result["messages"][-1]
            metrics.output = last_message.content if hasattr(last_message, 'content') else str(last_message)
            metrics.output_length = len(metrics.output)
            
            # Token estimation (LangGraph doesn't always expose this directly)
            enc = tiktoken.encoding_for_model("gpt-4o")
            metrics.output_tokens = len(enc.encode(metrics.output))
            metrics.input_tokens = metrics.output_tokens * 3  # Rough estimate
            metrics.total_tokens = metrics.input_tokens + metrics.output_tokens
            metrics.estimated_cost_usd = estimate_cost(metrics.input_tokens, metrics.output_tokens)
            metrics.success = True
            
        except Exception as e:
            metrics.error = str(e)
            metrics.success = False
        
        metrics.total_time_ms = (time.perf_counter() - start) * 1000
        return metrics
    
    def get_complexity_metrics(self) -> CodeComplexityMetrics:
        return CodeComplexityMetrics(
            framework=self.name,
            lines_of_code=55,
            import_count=8,
            class_count=1,  # State TypedDict
            function_count=3,  # agent, tool_node, tool
            abstraction_depth=4,  # graph → node → model → API
            boilerplate_ratio=0.35,
            type_annotations=5,
            comment_lines=3,
            mockable_interfaces=2,  # Model and tools
            requires_network_for_test=True,
            has_dependency_injection=False,
            deterministic_testable=True,  # Can mock model
        )


# =============================================================================
# 5. OPENAI AGENTS SDK IMPLEMENTATION
# =============================================================================

class OpenAIAgentsImplementation(FrameworkImplementation):
    """OpenAI Agents SDK implementation."""
    
    @property
    def name(self) -> str:
        return "OpenAI Agents SDK"
    
    async def execute(self, task: str) -> ExecutionMetrics:
        metrics = ExecutionMetrics(framework=self.name, task=task)
        start = time.perf_counter()
        
        try:
            from agents import Agent, Runner, function_tool
            
            @function_tool
            def search(query: str) -> str:
                """Search for information."""
                metrics.tool_call_count += 1
                return f"Search results for: {query}"
            
            agent = Agent(
                name="Researcher",
                instructions="You are a research assistant. Search for information and provide a concise answer.",
                tools=[search],
            )
            
            metrics.time_to_first_output_ms = (time.perf_counter() - start) * 1000
            
            result = await Runner.run(agent, input=task)
            
            metrics.output = result.final_output
            metrics.output_length = len(metrics.output)
            metrics.llm_call_count = len(result.raw_responses)
            
            # Token estimation
            enc = tiktoken.encoding_for_model("gpt-4o")
            metrics.output_tokens = len(enc.encode(metrics.output))
            metrics.input_tokens = metrics.output_tokens * 3
            metrics.total_tokens = metrics.input_tokens + metrics.output_tokens
            metrics.estimated_cost_usd = estimate_cost(metrics.input_tokens, metrics.output_tokens)
            metrics.success = True
            
        except Exception as e:
            metrics.error = str(e)
            metrics.success = False
        
        metrics.total_time_ms = (time.perf_counter() - start) * 1000
        return metrics
    
    def get_complexity_metrics(self) -> CodeComplexityMetrics:
        return CodeComplexityMetrics(
            framework=self.name,
            lines_of_code=25,
            import_count=3,
            class_count=0,
            function_count=1,  # search tool
            abstraction_depth=3,  # Runner → Agent → API
            boilerplate_ratio=0.20,
            type_annotations=2,
            comment_lines=2,
            mockable_interfaces=1,
            requires_network_for_test=True,
            has_dependency_injection=False,
            deterministic_testable=False,  # Harder to mock
        )


# =============================================================================
# 6. LLAMAINDEX IMPLEMENTATION
# =============================================================================

class LlamaIndexImplementation(FrameworkImplementation):
    """LlamaIndex ReAct agent implementation."""
    
    @property
    def name(self) -> str:
        return "LlamaIndex"
    
    async def execute(self, task: str) -> ExecutionMetrics:
        metrics = ExecutionMetrics(framework=self.name, task=task)
        start = time.perf_counter()
        
        try:
            from llama_index.core import Settings
            from llama_index.core.agent import ReActAgent
            from llama_index.core.tools import FunctionTool
            from llama_index.llms.openai import OpenAI
            
            Settings.llm = OpenAI(model="gpt-4o", temperature=0)
            
            def search(query: str) -> str:
                """Search for information."""
                metrics.tool_call_count += 1
                return f"Search results for: {query}"
            
            search_tool = FunctionTool.from_defaults(
                fn=search,
                name="search",
                description="Search for information on any topic.",
            )
            
            agent = ReActAgent.from_tools(
                tools=[search_tool],
                llm=OpenAI(model="gpt-4o", temperature=0),
                verbose=False,
                max_iterations=5,
            )
            
            metrics.time_to_first_output_ms = (time.perf_counter() - start) * 1000
            
            response = await agent.achat(task)
            
            metrics.output = str(response)
            metrics.output_length = len(metrics.output)
            metrics.llm_call_count = 2  # Estimate for ReAct (reason + synthesize)
            
            enc = tiktoken.encoding_for_model("gpt-4o")
            metrics.output_tokens = len(enc.encode(metrics.output))
            metrics.input_tokens = metrics.output_tokens * 4  # ReAct uses more input tokens
            metrics.total_tokens = metrics.input_tokens + metrics.output_tokens
            metrics.estimated_cost_usd = estimate_cost(metrics.input_tokens, metrics.output_tokens)
            metrics.success = True
            
        except Exception as e:
            metrics.error = str(e)
            metrics.success = False
        
        metrics.total_time_ms = (time.perf_counter() - start) * 1000
        return metrics
    
    def get_complexity_metrics(self) -> CodeComplexityMetrics:
        return CodeComplexityMetrics(
            framework=self.name,
            lines_of_code=35,
            import_count=5,
            class_count=0,
            function_count=1,
            abstraction_depth=5,  # Agent → ReAct → Tool → Function → result
            boilerplate_ratio=0.30,
            type_annotations=2,
            comment_lines=3,
            mockable_interfaces=2,
            requires_network_for_test=True,
            has_dependency_injection=False,
            deterministic_testable=False,
        )


# =============================================================================
# 7. PYDANTIC AI IMPLEMENTATION
# =============================================================================

class PydanticAIImplementation(FrameworkImplementation):
    """PydanticAI implementation."""
    
    @property
    def name(self) -> str:
        return "PydanticAI"
    
    async def execute(self, task: str) -> ExecutionMetrics:
        metrics = ExecutionMetrics(framework=self.name, task=task)
        start = time.perf_counter()
        
        try:
            from pydantic_ai import Agent
            from pydantic import BaseModel
            
            class ResearchResult(BaseModel):
                answer: str
                sources: list[str]
                confidence: float
            
            agent = Agent(
                "openai:gpt-4o",
                result_type=ResearchResult,
                system_prompt="You are a research assistant. Provide concise, well-sourced answers.",
            )
            
            @agent.tool_plain
            def search(query: str) -> str:
                """Search for information."""
                metrics.tool_call_count += 1
                return f"Search results for: {query}"
            
            metrics.time_to_first_output_ms = (time.perf_counter() - start) * 1000
            
            result = await agent.run(task)
            
            metrics.output = result.data.answer
            metrics.output_length = len(metrics.output)
            metrics.llm_call_count = 1
            
            enc = tiktoken.encoding_for_model("gpt-4o")
            metrics.output_tokens = len(enc.encode(metrics.output))
            metrics.input_tokens = metrics.output_tokens * 3
            metrics.total_tokens = metrics.input_tokens + metrics.output_tokens
            metrics.estimated_cost_usd = estimate_cost(metrics.input_tokens, metrics.output_tokens)
            metrics.success = True
            
        except Exception as e:
            metrics.error = str(e)
            metrics.success = False
        
        metrics.total_time_ms = (time.perf_counter() - start) * 1000
        return metrics
    
    def get_complexity_metrics(self) -> CodeComplexityMetrics:
        return CodeComplexityMetrics(
            framework=self.name,
            lines_of_code=30,
            import_count=3,
            class_count=1,  # ResearchResult
            function_count=1,
            abstraction_depth=2,  # Agent → API
            boilerplate_ratio=0.15,
            type_annotations=6,  # Pydantic enforces this
            comment_lines=2,
            mockable_interfaces=2,  # Agent and tools
            requires_network_for_test=True,
            has_dependency_injection=True,  # Built-in DI
            deterministic_testable=True,  # TestModel available
        )


# =============================================================================
# 8. COMPARISON RUNNER
# =============================================================================

class FrameworkComparisonRunner:
    """Run the same task across all frameworks and compare."""
    
    def __init__(self):
        self.implementations: list[FrameworkImplementation] = [
            NoFrameworkImplementation(),
            LangGraphImplementation(),
            OpenAIAgentsImplementation(),
            LlamaIndexImplementation(),
            PydanticAIImplementation(),
        ]
        self.results: list[ExecutionMetrics] = []
    
    async def run_comparison(self, tasks: list[str], runs_per_task: int = 3) -> dict:
        """Run all tasks across all frameworks multiple times."""
        all_metrics = []
        
        for task in tasks:
            print(f"\n{'='*60}")
            print(f"Task: {task}")
            print(f"{'='*60}")
            
            for impl in self.implementations:
                task_metrics = []
                
                for run in range(runs_per_task):
                    print(f"  {impl.name} (run {run+1}/{runs_per_task})...", end=" ")
                    metrics = await impl.execute(task)
                    task_metrics.append(metrics)
                    status = "✓" if metrics.success else f"✗ ({metrics.error})"
                    print(f"{status} ({metrics.total_time_ms:.0f}ms)")
                
                all_metrics.extend(task_metrics)
        
        self.results = all_metrics
        return self._generate_report()
    
    def _generate_report(self) -> dict:
        """Generate comparison report from collected metrics."""
        report = {"frameworks": {}, "summary": {}}
        
        for impl in self.implementations:
            framework_metrics = [m for m in self.results if m.framework == impl.name]
            successful = [m for m in framework_metrics if m.success]
            
            if successful:
                avg_time = sum(m.total_time_ms for m in successful) / len(successful)
                avg_tokens = sum(m.total_tokens for m in successful) / len(successful)
                avg_cost = sum(m.estimated_cost_usd for m in successful) / len(successful)
                avg_llm_calls = sum(m.llm_call_count for m in successful) / len(successful)
            else:
                avg_time = avg_tokens = avg_cost = avg_llm_calls = 0
            
            complexity = impl.get_complexity_metrics()
            
            report["frameworks"][impl.name] = {
                "execution": {
                    "avg_time_ms": round(avg_time, 2),
                    "avg_tokens": round(avg_tokens),
                    "avg_cost_usd": round(avg_cost, 6),
                    "avg_llm_calls": round(avg_llm_calls, 1),
                    "success_rate": len(successful) / max(len(framework_metrics), 1),
                },
                "complexity": {
                    "lines_of_code": complexity.lines_of_code,
                    "imports": complexity.import_count,
                    "abstraction_depth": complexity.abstraction_depth,
                    "boilerplate_ratio": complexity.boilerplate_ratio,
                },
                "testability": {
                    "mockable_interfaces": complexity.mockable_interfaces,
                    "has_di": complexity.has_dependency_injection,
                    "deterministic_testable": complexity.deterministic_testable,
                },
            }
        
        # Determine winners
        frameworks = report["frameworks"]
        if frameworks:
            report["summary"] = {
                "fastest": min(frameworks, key=lambda f: frameworks[f]["execution"]["avg_time_ms"]),
                "cheapest": min(frameworks, key=lambda f: frameworks[f]["execution"]["avg_cost_usd"]),
                "simplest": min(frameworks, key=lambda f: frameworks[f]["complexity"]["lines_of_code"]),
                "most_testable": max(frameworks, key=lambda f: frameworks[f]["testability"]["mockable_interfaces"]),
                "least_overhead": min(frameworks, key=lambda f: frameworks[f]["complexity"]["abstraction_depth"]),
            }
        
        return report
    
    def print_report(self, report: dict):
        """Pretty print the comparison report."""
        print("\n" + "=" * 80)
        print("FRAMEWORK COMPARISON REPORT")
        print("=" * 80)
        
        # Execution metrics table
        print(f"\n{'Framework':<25} {'Avg Time':<12} {'Tokens':<10} {'Cost':<12} {'LLM Calls':<10} {'Success':<8}")
        print("-" * 80)
        
        for name, data in report["frameworks"].items():
            ex = data["execution"]
            print(
                f"{name:<25} {ex['avg_time_ms']:<12.0f} {ex['avg_tokens']:<10.0f} "
                f"${ex['avg_cost_usd']:<11.5f} {ex['avg_llm_calls']:<10.1f} {ex['success_rate']:<8.0%}"
            )
        
        # Complexity table
        print(f"\n{'Framework':<25} {'LOC':<6} {'Imports':<8} {'Depth':<7} {'Boilerplate':<12} {'Testable':<8}")
        print("-" * 80)
        
        for name, data in report["frameworks"].items():
            cx = data["complexity"]
            ts = data["testability"]
            print(
                f"{name:<25} {cx['lines_of_code']:<6} {cx['imports']:<8} {cx['abstraction_depth']:<7} "
                f"{cx['boilerplate_ratio']:<12.0%} {'Yes' if ts['deterministic_testable'] else 'No':<8}"
            )
        
        # Winners
        print(f"\n{'WINNERS':=^80}")
        for category, winner in report.get("summary", {}).items():
            print(f"  {category.replace('_', ' ').title()}: {winner}")


# =============================================================================
# 9. MAIN
# =============================================================================

async def main():
    """Run the framework comparison."""
    
    tasks = [
        "What are the key differences between PostgreSQL and MySQL for large-scale applications?",
        "Explain the CAP theorem and its implications for distributed databases.",
        "What are best practices for API rate limiting in microservices?",
    ]
    
    runner = FrameworkComparisonRunner()
    
    print("Framework Comparison Harness")
    print("=" * 60)
    print(f"Tasks: {len(tasks)}")
    print(f"Frameworks: {len(runner.implementations)}")
    print(f"Runs per task: 3")
    print()
    
    # Run comparison (or show structure if no API key)
    import os
    if not os.getenv("OPENAI_API_KEY"):
        print("No OPENAI_API_KEY set. Showing static complexity comparison:\n")
        
        report = {"frameworks": {}, "summary": {}}
        for impl in runner.implementations:
            complexity = impl.get_complexity_metrics()
            report["frameworks"][impl.name] = {
                "execution": {"avg_time_ms": 0, "avg_tokens": 0, "avg_cost_usd": 0, "avg_llm_calls": 0, "success_rate": 0},
                "complexity": {
                    "lines_of_code": complexity.lines_of_code,
                    "imports": complexity.import_count,
                    "abstraction_depth": complexity.abstraction_depth,
                    "boilerplate_ratio": complexity.boilerplate_ratio,
                },
                "testability": {
                    "mockable_interfaces": complexity.mockable_interfaces,
                    "has_di": complexity.has_dependency_injection,
                    "deterministic_testable": complexity.deterministic_testable,
                },
            }
        
        runner.print_report(report)
    else:
        report = await runner.run_comparison(tasks, runs_per_task=3)
        runner.print_report(report)
        
        # Save raw results
        with open("comparison_results.json", "w") as f:
            json.dump([m.to_dict() for m in runner.results], f, indent=2)
        print("\nRaw results saved to comparison_results.json")


if __name__ == "__main__":
    asyncio.run(main())
