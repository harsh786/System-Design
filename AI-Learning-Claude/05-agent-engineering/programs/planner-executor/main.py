"""
Planner-Executor Agent
======================
Separates planning from execution. The Planner creates a structured plan,
the Executor runs each step, and re-planning occurs on failure.
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =============================================================================
# SIMULATED TOOLS (for the executor)
# =============================================================================

def research(topic: str) -> str:
    """Simulated research tool."""
    research_db = {
        "fastapi": "FastAPI: Modern Python web framework. Async, auto-docs, type-safe. Performance comparable to Node.js. Great for APIs.",
        "django": "Django: Batteries-included Python framework. ORM, admin, auth built-in. Mature ecosystem. Better for full-stack apps.",
        "express": "Express.js: Minimal Node.js framework. Huge ecosystem, flexible, widely used. Less opinionated.",
        "postgresql": "PostgreSQL: Advanced open-source RDBMS. ACID, JSON support, extensions. Best for complex queries.",
        "mongodb": "MongoDB: Document database. Flexible schema, horizontal scaling. Good for rapid prototyping.",
        "redis": "Redis: In-memory data store. Caching, pub/sub, queues. Sub-millisecond latency.",
        "react": "React: Component-based UI library by Meta. Virtual DOM, huge ecosystem, JSX.",
        "vue": "Vue.js: Progressive framework. Easy learning curve, good docs, reactive data binding.",
        "docker": "Docker: Containerization platform. Consistent environments, easy deployment, microservices.",
        "kubernetes": "Kubernetes: Container orchestration. Auto-scaling, self-healing, service discovery. Complex but powerful.",
    }
    topic_lower = topic.lower()
    for key, value in research_db.items():
        if key in topic_lower:
            return value
    return f"Research on '{topic}': General-purpose technology. Evaluate based on team expertise and project requirements."


def compare(items: str) -> str:
    """Simulated comparison tool."""
    return f"Comparison of {items}: Each option has trade-offs. Consider: team expertise, scalability needs, time-to-market, and long-term maintenance."


def recommend(criteria: str) -> str:
    """Simulated recommendation tool."""
    return f"Based on criteria ({criteria}): Recommend the option that best balances team familiarity, project requirements, and scalability needs."


TOOLS = {
    "research": research,
    "compare": compare,
    "recommend": recommend,
}

# =============================================================================
# PLANNER AGENT
# =============================================================================

PLANNER_PROMPT = """You are a planning agent. Given a complex task, create a step-by-step plan.

Output a JSON plan with this structure:
{
  "goal": "the overall goal",
  "steps": [
    {"id": 1, "action": "research|compare|recommend", "input": "what to research/compare/recommend", "depends_on": []},
    {"id": 2, "action": "...", "input": "...", "depends_on": [1]}
  ]
}

Available actions:
- research: Look up information about a technology or topic
- compare: Compare multiple items/options
- recommend: Make a recommendation based on criteria

Rules:
- Steps that don't depend on each other should have empty depends_on
- Each step should be atomic (one clear action)
- Maximum 8 steps
- Output ONLY valid JSON, no other text
"""


def create_plan(task: str) -> dict:
    """Use the Planner LLM to create a structured plan."""
    print("\n📐 PLANNER: Creating plan...")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": PLANNER_PROMPT},
            {"role": "user", "content": f"Task: {task}"},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )

    plan = json.loads(response.choices[0].message.content)
    return plan


def replan(original_task: str, completed_steps: list, failed_step: dict, error: str) -> dict:
    """Re-plan after a failure."""
    print("\n🔄 PLANNER: Re-planning after failure...")

    context = f"""Original task: {original_task}

Completed steps and their results:
{json.dumps(completed_steps, indent=2)}

Failed step: {json.dumps(failed_step)}
Error: {error}

Create a new plan to complete the remaining work, taking into account what was already done and what failed.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": PLANNER_PROMPT},
            {"role": "user", "content": context},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )

    plan = json.loads(response.choices[0].message.content)
    return plan


# =============================================================================
# EXECUTOR AGENT
# =============================================================================

EXECUTOR_PROMPT = """You are an executor agent. Given a step to execute and available context,
execute the step using the provided tool and return a clear, concise result.

Synthesize the tool output into a useful summary for the next steps."""


def execute_step(step: dict, context: dict) -> str:
    """Execute a single step of the plan."""
    action = step["action"]
    step_input = step["input"]

    # Call the tool
    if action in TOOLS:
        tool_result = TOOLS[action](step_input)
    else:
        raise ValueError(f"Unknown action: {action}")

    # Use LLM to synthesize the result
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": EXECUTOR_PROMPT},
            {"role": "user", "content": f"Step: {step['action']} - {step['input']}\nTool result: {tool_result}\nContext from previous steps: {json.dumps(context)}\n\nProvide a concise summary of what was learned/accomplished."},
        ],
        temperature=0,
        max_tokens=200,
    )

    return response.choices[0].message.content


# =============================================================================
# PLAN VALIDATION
# =============================================================================

def validate_plan(plan: dict) -> list[str]:
    """Validate a plan before execution."""
    errors = []

    if "steps" not in plan:
        errors.append("Plan has no 'steps' field")
        return errors

    step_ids = {s["id"] for s in plan["steps"]}

    for step in plan["steps"]:
        if step["action"] not in TOOLS:
            errors.append(f"Step {step['id']}: unknown action '{step['action']}'")
        for dep in step.get("depends_on", []):
            if dep not in step_ids:
                errors.append(f"Step {step['id']}: dependency on non-existent step {dep}")
            if dep >= step["id"]:
                errors.append(f"Step {step['id']}: circular dependency on step {dep}")

    if len(plan["steps"]) > 8:
        errors.append(f"Plan has {len(plan['steps'])} steps (max 8)")

    return errors


# =============================================================================
# ORCHESTRATOR - Runs the full planner-executor loop
# =============================================================================

def run_planner_executor(task: str, max_replans: int = 2):
    """Run the full planner-executor pipeline."""
    print("=" * 60)
    print(f"🎯 TASK: {task}")
    print("=" * 60)

    # Phase 1: Plan
    plan = create_plan(task)
    print(f"\n📋 PLAN: {plan.get('goal', task)}")
    print(f"   Steps: {len(plan.get('steps', []))}")
    for step in plan.get("steps", []):
        deps = f" (after step {step['depends_on']})" if step.get("depends_on") else ""
        print(f"   {step['id']}. [{step['action']}] {step['input']}{deps}")

    # Validate
    errors = validate_plan(plan)
    if errors:
        print(f"\n❌ Plan validation failed:")
        for e in errors:
            print(f"   - {e}")
        return

    print(f"\n✅ Plan validated successfully")

    # Phase 2: Execute
    print(f"\n{'─' * 40}")
    print("⚡ EXECUTING PLAN")
    print(f"{'─' * 40}")

    results = {}
    completed_steps = []
    replans = 0

    for step in plan.get("steps", []):
        step_id = step["id"]

        # Check dependencies are met
        for dep in step.get("depends_on", []):
            if dep not in results:
                print(f"   ⚠️  Step {step_id}: waiting for dependency {dep} (skipped)")
                continue

        print(f"\n   Step {step_id}: [{step['action']}] {step['input']}")

        try:
            # Build context from completed dependencies
            context = {k: v for k, v in results.items() if k in step.get("depends_on", [])}
            result = execute_step(step, context)
            results[step_id] = result
            completed_steps.append({"step": step, "result": result})
            print(f"   ✅ Result: {result[:150]}...")

        except Exception as e:
            print(f"   ❌ FAILED: {str(e)}")

            if replans < max_replans:
                replans += 1
                plan = replan(task, completed_steps, step, str(e))
                print(f"\n   🔄 New plan created (replan {replans}/{max_replans})")
                # In production, you'd restart execution with the new plan
                break
            else:
                print(f"   ⚠️  Max replans reached. Continuing with partial results.")

    # Phase 3: Final synthesis
    print(f"\n{'─' * 40}")
    print("📝 FINAL SYNTHESIS")
    print(f"{'─' * 40}")

    synthesis_response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Synthesize the following research results into a clear, actionable recommendation."},
            {"role": "user", "content": f"Task: {task}\n\nResults from each step:\n{json.dumps(completed_steps, indent=2)}"},
        ],
        temperature=0,
        max_tokens=500,
    )

    final = synthesis_response.choices[0].message.content
    print(f"\n{final}")
    print(f"\n{'=' * 60}")
    print(f"✅ Task completed. Steps executed: {len(completed_steps)}, Replans: {replans}")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    task = """Research and recommend a tech stack for a new SaaS startup building a 
    project management tool. Consider: backend framework (FastAPI vs Django), 
    database (PostgreSQL vs MongoDB), frontend (React vs Vue), and deployment (Docker vs Kubernetes).
    Compare options and provide a final recommendation."""

    run_planner_executor(task)
