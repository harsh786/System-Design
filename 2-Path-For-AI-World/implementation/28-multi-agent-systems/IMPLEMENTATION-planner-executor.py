"""
Multi-Agent Systems: Planner-Executor Pattern
==============================================

Production implementation of the planner-executor pattern where a planner agent
creates step-by-step plans and an executor agent carries them out, with support
for replanning, checkpoints, human approval, and cost estimation.
"""

import asyncio
import uuid
import time
import json
from enum import Enum
from typing import Any, Optional
from dataclasses import dataclass, field


# =============================================================================
# Core Types
# =============================================================================

class StepStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    NEEDS_REPLAN = "needs_replan"


class PlanStatus(Enum):
    DRAFT = "draft"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REPLANNING = "replanning"


@dataclass
class PlanStep:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    action: str = ""  # tool/function to execute
    input_data: dict = field(default_factory=dict)
    expected_output: str = ""
    success_criteria: str = ""
    dependencies: list[str] = field(default_factory=list)
    estimated_cost: float = 0.0
    estimated_time: float = 0.0  # seconds
    requires_approval: bool = False
    status: StepStatus = StepStatus.PENDING
    result: Optional[dict] = None
    error: Optional[str] = None
    actual_cost: float = 0.0
    actual_time: float = 0.0
    attempt: int = 0
    max_attempts: int = 2


@dataclass
class Plan:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    goal: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    status: PlanStatus = PlanStatus.DRAFT
    version: int = 1
    estimated_total_cost: float = 0.0
    estimated_total_time: float = 0.0
    actual_total_cost: float = 0.0
    actual_total_time: float = 0.0
    created_at: float = field(default_factory=time.time)
    checkpoints: list[dict] = field(default_factory=list)
    replan_history: list[dict] = field(default_factory=list)


# =============================================================================
# Planner Agent
# =============================================================================

class PlannerAgent:
    """
    Creates, validates, and refines execution plans.
    Responsible for strategic thinking — what to do and in what order.
    """

    def __init__(self, max_steps: int = 10, max_cost_per_plan: float = 1.0):
        self.max_steps = max_steps
        self.max_cost_per_plan = max_cost_per_plan

    async def create_plan(self, goal: str, context: dict = None) -> Plan:
        """
        Create a step-by-step plan for achieving the goal.
        In production: LLM call with structured output.
        """
        # Simulated planning — in production this is an LLM call
        await asyncio.sleep(0.3)
        
        plan = Plan(goal=goal)
        
        # Analyze goal and create appropriate steps
        steps = await self._decompose_goal(goal, context or {})
        plan.steps = steps
        
        # Calculate estimates
        plan.estimated_total_cost = sum(s.estimated_cost for s in steps)
        plan.estimated_total_time = self._estimate_total_time(steps)
        
        # Validate plan
        validation = await self.validate_plan(plan)
        if not validation["valid"]:
            # Auto-fix common issues
            plan = await self._fix_plan(plan, validation["issues"])
        
        plan.status = PlanStatus.AWAITING_APPROVAL
        return plan

    async def _decompose_goal(self, goal: str, context: dict) -> list[PlanStep]:
        """Decompose goal into ordered steps with dependencies."""
        steps = []
        
        # Step 1: Research/Understand
        research_step = PlanStep(
            description=f"Research and understand requirements for: {goal}",
            action="research",
            input_data={"query": goal, "depth": "comprehensive"},
            expected_output="Summary of findings with key insights",
            success_criteria="At least 3 relevant findings identified",
            estimated_cost=0.01,
            estimated_time=5.0,
        )
        steps.append(research_step)
        
        # Step 2: Design/Plan approach
        design_step = PlanStep(
            description="Design the solution approach based on research",
            action="design",
            input_data={"research_context": "from_step_1"},
            expected_output="Detailed design document with architecture decisions",
            success_criteria="Design covers all requirements and edge cases",
            dependencies=[research_step.id],
            estimated_cost=0.02,
            estimated_time=8.0,
        )
        steps.append(design_step)
        
        # Step 3: Implement
        impl_step = PlanStep(
            description="Implement the solution according to design",
            action="implement",
            input_data={"design": "from_step_2"},
            expected_output="Working implementation with code",
            success_criteria="Code compiles/runs without errors",
            dependencies=[design_step.id],
            estimated_cost=0.05,
            estimated_time=15.0,
            requires_approval=True,  # Implementation needs human review
        )
        steps.append(impl_step)
        
        # Step 4: Validate
        validate_step = PlanStep(
            description="Validate the implementation against requirements",
            action="validate",
            input_data={"implementation": "from_step_3", "requirements": goal},
            expected_output="Validation report with pass/fail for each requirement",
            success_criteria="All critical requirements pass validation",
            dependencies=[impl_step.id],
            estimated_cost=0.02,
            estimated_time=5.0,
        )
        steps.append(validate_step)
        
        # Step 5: Document
        doc_step = PlanStep(
            description="Document the solution and decisions made",
            action="document",
            input_data={"implementation": "from_step_3", "design": "from_step_2"},
            expected_output="Documentation covering usage, architecture, decisions",
            success_criteria="Documentation is clear and complete",
            dependencies=[validate_step.id],
            estimated_cost=0.01,
            estimated_time=5.0,
        )
        steps.append(doc_step)
        
        return steps

    def _estimate_total_time(self, steps: list[PlanStep]) -> float:
        """Estimate total time accounting for parallelism and dependencies."""
        # Simple critical path estimation
        # In production: build dependency DAG and compute critical path
        return sum(s.estimated_time for s in steps) * 0.7  # Assume 30% parallelism

    async def validate_plan(self, plan: Plan) -> dict:
        """Validate plan for completeness, feasibility, and cost."""
        issues = []
        
        # Check step count
        if len(plan.steps) > self.max_steps:
            issues.append(f"Too many steps ({len(plan.steps)} > {self.max_steps})")
        
        # Check cost
        if plan.estimated_total_cost > self.max_cost_per_plan:
            issues.append(f"Estimated cost too high (${plan.estimated_total_cost:.2f} > ${self.max_cost_per_plan:.2f})")
        
        # Check dependencies (no cycles, all referenced steps exist)
        step_ids = {s.id for s in plan.steps}
        for step in plan.steps:
            for dep in step.dependencies:
                if dep not in step_ids:
                    issues.append(f"Step {step.id} depends on non-existent step {dep}")
        
        # Check for cycles
        if self._has_cycles(plan.steps):
            issues.append("Dependency cycle detected")
        
        # Each step should have success criteria
        for step in plan.steps:
            if not step.success_criteria:
                issues.append(f"Step {step.id} missing success criteria")
        
        return {"valid": len(issues) == 0, "issues": issues}

    def _has_cycles(self, steps: list[PlanStep]) -> bool:
        """Detect dependency cycles using DFS."""
        step_map = {s.id: s for s in steps}
        visited = set()
        rec_stack = set()
        
        def dfs(step_id):
            visited.add(step_id)
            rec_stack.add(step_id)
            step = step_map.get(step_id)
            if step:
                for dep in step.dependencies:
                    if dep not in visited:
                        if dfs(dep):
                            return True
                    elif dep in rec_stack:
                        return True
            rec_stack.discard(step_id)
            return False
        
        for s in steps:
            if s.id not in visited:
                if dfs(s.id):
                    return True
        return False

    async def _fix_plan(self, plan: Plan, issues: list[str]) -> Plan:
        """Attempt to auto-fix plan issues."""
        # In production: LLM re-plans with issue context
        for step in plan.steps:
            if not step.success_criteria:
                step.success_criteria = f"Step '{step.description}' produces expected output"
        return plan

    async def replan(self, plan: Plan, failure_context: dict) -> Plan:
        """
        Create a new plan after a failure, incorporating lessons learned.
        """
        plan.status = PlanStatus.REPLANNING
        plan.version += 1
        
        # Record replan event
        plan.replan_history.append({
            "version": plan.version,
            "reason": failure_context.get("reason", "unknown"),
            "failed_step": failure_context.get("step_id"),
            "timestamp": time.time(),
        })
        
        # In production: LLM call with failure context to create better plan
        await asyncio.sleep(0.2)
        
        # Simple strategy: skip failed step's approach, try alternative
        failed_step_id = failure_context.get("step_id")
        for step in plan.steps:
            if step.id == failed_step_id:
                step.status = StepStatus.SKIPPED
                # Insert alternative step
                alt_step = PlanStep(
                    description=f"[Alternative] {step.description}",
                    action=f"{step.action}_alternative",
                    input_data={**step.input_data, "previous_failure": failure_context},
                    expected_output=step.expected_output,
                    success_criteria=step.success_criteria,
                    dependencies=step.dependencies,
                    estimated_cost=step.estimated_cost * 1.5,
                    estimated_time=step.estimated_time * 1.5,
                )
                # Insert after failed step
                idx = plan.steps.index(step)
                plan.steps.insert(idx + 1, alt_step)
                
                # Update dependencies pointing to failed step
                for other_step in plan.steps:
                    if failed_step_id in other_step.dependencies:
                        other_step.dependencies = [
                            alt_step.id if d == failed_step_id else d
                            for d in other_step.dependencies
                        ]
                break
        
        plan.status = PlanStatus.APPROVED  # Auto-approve replans (or require approval)
        return plan


# =============================================================================
# Executor Agent
# =============================================================================

class ExecutorAgent:
    """
    Executes individual plan steps. Stateless — doesn't know the overall plan.
    Has access to tools and returns structured results.
    """

    def __init__(self):
        self.tools = {
            "research": self._tool_research,
            "design": self._tool_design,
            "implement": self._tool_implement,
            "validate": self._tool_validate,
            "document": self._tool_document,
        }

    async def execute_step(self, step: PlanStep, 
                          prior_results: dict[str, dict]) -> dict:
        """Execute a single plan step with context from prior steps."""
        # Resolve references to prior step outputs
        resolved_input = self._resolve_references(step.input_data, prior_results)
        
        # Find the appropriate tool
        tool_fn = self.tools.get(step.action)
        if not tool_fn:
            # Try without suffix (for alternative actions)
            base_action = step.action.replace("_alternative", "")
            tool_fn = self.tools.get(base_action)
        
        if not tool_fn:
            return {
                "success": False,
                "error": f"Unknown action: {step.action}",
                "output": None,
            }
        
        # Execute
        try:
            result = await tool_fn(resolved_input, step)
            
            # Check success criteria
            meets_criteria = await self._check_success_criteria(
                result, step.success_criteria
            )
            
            return {
                "success": meets_criteria,
                "output": result,
                "error": None if meets_criteria else "Did not meet success criteria",
                "cost": result.get("cost", 0),
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "output": None,
                "cost": 0,
            }

    def _resolve_references(self, input_data: dict, prior_results: dict) -> dict:
        """Replace references like 'from_step_1' with actual results."""
        resolved = {}
        for key, value in input_data.items():
            if isinstance(value, str) and value.startswith("from_step_"):
                # Find the referenced step's output
                for step_id, result in prior_results.items():
                    if result:  # Use latest available result
                        resolved[key] = result
                        break
                else:
                    resolved[key] = value  # Keep reference if not found
            else:
                resolved[key] = value
        return resolved

    async def _check_success_criteria(self, result: dict, criteria: str) -> bool:
        """Check if result meets success criteria. In production: LLM evaluation."""
        # Simplified check — in production this would be an LLM evaluation
        if not result:
            return False
        return result.get("quality", 0.8) >= 0.6

    # --- Tools ---

    async def _tool_research(self, input_data: dict, step: PlanStep) -> dict:
        await asyncio.sleep(0.5)
        return {
            "findings": ["Finding A", "Finding B", "Finding C"],
            "sources": 3,
            "quality": 0.85,
            "cost": 0.01,
        }

    async def _tool_design(self, input_data: dict, step: PlanStep) -> dict:
        await asyncio.sleep(0.6)
        return {
            "design": "Architecture design document...",
            "components": ["Component A", "Component B"],
            "quality": 0.82,
            "cost": 0.02,
        }

    async def _tool_implement(self, input_data: dict, step: PlanStep) -> dict:
        await asyncio.sleep(1.0)
        return {
            "code": "def solution(): ...",
            "files_created": 3,
            "tests_passing": True,
            "quality": 0.88,
            "cost": 0.05,
        }

    async def _tool_validate(self, input_data: dict, step: PlanStep) -> dict:
        await asyncio.sleep(0.4)
        return {
            "all_passing": True,
            "tests_run": 12,
            "tests_passed": 11,
            "coverage": 0.85,
            "quality": 0.9,
            "cost": 0.02,
        }

    async def _tool_document(self, input_data: dict, step: PlanStep) -> dict:
        await asyncio.sleep(0.4)
        return {
            "document": "# Solution Documentation\n...",
            "sections": 4,
            "quality": 0.87,
            "cost": 0.01,
        }


# =============================================================================
# Plan Execution Engine
# =============================================================================

class PlanExecutionEngine:
    """
    Orchestrates plan execution: runs steps in dependency order,
    handles failures, checkpoints, and replanning.
    """

    def __init__(self, planner: PlannerAgent, executor: ExecutorAgent,
                 human_approval_fn: Optional[Any] = None,
                 max_replans: int = 2,
                 global_timeout: float = 120.0,
                 global_budget: float = 1.0):
        self.planner = planner
        self.executor = executor
        self.human_approval_fn = human_approval_fn or self._auto_approve
        self.max_replans = max_replans
        self.global_timeout = global_timeout
        self.global_budget = global_budget
        self.execution_log: list[dict] = []

    async def run(self, goal: str, context: dict = None) -> dict:
        """Full lifecycle: plan → approve → execute → replan if needed."""
        start_time = time.time()
        
        # Phase 1: Create plan
        print(f"\n  [Planner] Creating plan for: {goal}")
        plan = await self.planner.create_plan(goal, context)
        self._log("plan_created", plan.id, f"{len(plan.steps)} steps, est ${plan.estimated_total_cost:.3f}")
        
        # Print plan
        print(f"\n  [Plan v{plan.version}] {len(plan.steps)} steps:")
        for i, step in enumerate(plan.steps):
            deps = f" (deps: {step.dependencies})" if step.dependencies else ""
            approval = " ⚠️ NEEDS APPROVAL" if step.requires_approval else ""
            print(f"    {i+1}. [{step.action}] {step.description[:60]}{deps}{approval}")
        print(f"    Estimated: ${plan.estimated_total_cost:.3f}, {plan.estimated_total_time:.0f}s")
        
        # Phase 2: Get approval
        if not await self._get_plan_approval(plan):
            return {"status": "rejected", "plan": plan}
        
        plan.status = PlanStatus.APPROVED
        
        # Phase 3: Execute
        replans = 0
        while replans <= self.max_replans:
            plan.status = PlanStatus.EXECUTING
            result = await self._execute_plan(plan, start_time)
            
            if result["success"]:
                plan.status = PlanStatus.COMPLETED
                break
            elif result.get("needs_replan") and replans < self.max_replans:
                print(f"\n  [Planner] Replanning (attempt {replans + 1})...")
                plan = await self.planner.replan(plan, result["failure_context"])
                replans += 1
                self._log("replan", plan.id, f"v{plan.version}: {result['failure_context'].get('reason')}")
            else:
                plan.status = PlanStatus.FAILED
                break
        
        # Final summary
        elapsed = time.time() - start_time
        return {
            "status": plan.status.value,
            "plan_id": plan.id,
            "plan_version": plan.version,
            "steps_completed": sum(1 for s in plan.steps if s.status == StepStatus.COMPLETED),
            "steps_total": len(plan.steps),
            "total_cost": plan.actual_total_cost,
            "total_time": elapsed,
            "replans": replans,
            "results": {s.id: s.result for s in plan.steps if s.result},
        }

    async def _execute_plan(self, plan: Plan, start_time: float) -> dict:
        """Execute plan steps in dependency order."""
        completed_ids: set[str] = set()
        prior_results: dict[str, dict] = {}
        
        while True:
            # Budget/timeout checks
            if time.time() - start_time > self.global_timeout:
                return {"success": False, "needs_replan": False, 
                       "failure_context": {"reason": "global timeout"}}
            if plan.actual_total_cost > self.global_budget:
                return {"success": False, "needs_replan": False,
                       "failure_context": {"reason": "budget exceeded"}}
            
            # Find ready steps
            ready = [
                s for s in plan.steps
                if s.status in (StepStatus.PENDING, StepStatus.APPROVED)
                and all(d in completed_ids for d in s.dependencies)
            ]
            
            if not ready:
                # Check if all done
                all_done = all(
                    s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED) 
                    or s.attempt >= s.max_attempts
                    for s in plan.steps
                )
                if all_done:
                    all_success = all(
                        s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED)
                        for s in plan.steps
                    )
                    return {"success": all_success}
                
                await asyncio.sleep(0.1)
                continue
            
            # Execute ready steps (could be parallel if no shared deps)
            for step in ready:
                # Human approval gate
                if step.requires_approval:
                    print(f"\n  [Approval Required] Step: {step.description}")
                    approved = await self.human_approval_fn(step)
                    if not approved:
                        step.status = StepStatus.SKIPPED
                        completed_ids.add(step.id)
                        continue
                    step.status = StepStatus.APPROVED
                
                # Execute
                step.status = StepStatus.IN_PROGRESS
                step.attempt += 1
                step_start = time.time()
                
                print(f"  [Executor] Running: {step.description[:50]}...")
                result = await self.executor.execute_step(step, prior_results)
                
                step.actual_time = time.time() - step_start
                step.actual_cost = result.get("cost", 0)
                plan.actual_total_cost += step.actual_cost
                
                if result["success"]:
                    step.status = StepStatus.COMPLETED
                    step.result = result["output"]
                    prior_results[step.id] = result["output"]
                    completed_ids.add(step.id)
                    print(f"  [Executor] ✓ Completed (${step.actual_cost:.4f}, {step.actual_time:.1f}s)")
                    
                    # Checkpoint
                    self._checkpoint(plan, step)
                else:
                    step.error = result.get("error", "Unknown error")
                    print(f"  [Executor] ✗ Failed: {step.error}")
                    
                    if step.attempt >= step.max_attempts:
                        step.status = StepStatus.FAILED
                        return {
                            "success": False,
                            "needs_replan": True,
                            "failure_context": {
                                "step_id": step.id,
                                "reason": step.error,
                                "attempt": step.attempt,
                            }
                        }
                    else:
                        step.status = StepStatus.PENDING  # Retry
        
        return {"success": True}

    def _checkpoint(self, plan: Plan, completed_step: PlanStep):
        """Save checkpoint after step completion for resume capability."""
        plan.checkpoints.append({
            "step_id": completed_step.id,
            "timestamp": time.time(),
            "cost_so_far": plan.actual_total_cost,
            "steps_completed": sum(1 for s in plan.steps if s.status == StepStatus.COMPLETED),
        })

    async def _get_plan_approval(self, plan: Plan) -> bool:
        """Get human approval for the plan. Simulated as auto-approve."""
        print(f"\n  [Approval] Plan ready for review (auto-approving for demo)")
        return True

    async def _auto_approve(self, step: PlanStep) -> bool:
        """Auto-approve steps (for demo/testing)."""
        print(f"  [Approval] Auto-approving step: {step.description[:40]}...")
        return True

    def _log(self, event: str, plan_id: str, detail: str):
        self.execution_log.append({
            "timestamp": time.time(),
            "event": event,
            "plan_id": plan_id,
            "detail": detail,
        })


# =============================================================================
# Demo
# =============================================================================

async def main():
    print("=" * 70)
    print("PLANNER-EXECUTOR PATTERN DEMO")
    print("=" * 70)
    
    planner = PlannerAgent(max_steps=10, max_cost_per_plan=0.50)
    executor = ExecutorAgent()
    
    engine = PlanExecutionEngine(
        planner=planner,
        executor=executor,
        max_replans=2,
        global_timeout=60.0,
        global_budget=0.50,
    )
    
    # Run a complex task
    result = await engine.run(
        goal="Research and implement a rate limiter with sliding window algorithm",
        context={"language": "python", "testing_required": True}
    )
    
    print(f"\n{'=' * 70}")
    print("EXECUTION RESULT")
    print(f"{'=' * 70}")
    print(f"  Status: {result['status']}")
    print(f"  Steps: {result['steps_completed']}/{result['steps_total']} completed")
    print(f"  Cost: ${result['total_cost']:.4f}")
    print(f"  Time: {result['total_time']:.2f}s")
    print(f"  Replans: {result['replans']}")


if __name__ == "__main__":
    asyncio.run(main())
