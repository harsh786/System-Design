"""
Trajectory Recorder
===================
Records agent trajectories and creates golden trajectory datasets.
Demonstrates: trajectory schema, step recording, approval workflow, comparison.
"""

import json
import os
import time
import uuid
from datetime import datetime

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Simulated Tools ---
AVAILABLE_TOOLS = {
    "sql_query": "Query the database with SQL",
    "vector_search": "Search documents by semantic similarity",
    "calculator": "Perform mathematical calculations",
    "send_email": "Send an email to a recipient",
    "check_calendar": "Check calendar availability",
    "crm_lookup": "Look up customer information in CRM",
    "create_ticket": "Create a support ticket",
    "get_weather": "Get weather for a location"
}

# --- Simulated tool results ---
TOOL_RESULTS = {
    "sql_query": {
        "revenue_q3": {"rows": [{"quarter": "Q3", "revenue": 2300000}]},
        "overdue_invoices": {"rows": [{"id": "INV-001", "amount": 5000, "customer": "Acme"}, {"id": "INV-002", "amount": 12000, "customer": "Acme"}]},
        "customer_count": {"rows": [{"tier": "enterprise", "count": 45}]},
    },
    "vector_search": {
        "revenue_target": {"results": [{"text": "Q3 2024 revenue target: $2.0M", "score": 0.92, "source": "annual-plan.pdf"}]},
        "refund_policy": {"results": [{"text": "Enterprise: 60-day full refund. After 60 days, prorated with 10% fee.", "score": 0.95}]},
    },
    "calculator": {
        "percentage": {"result": 15.0},
        "sum": {"result": 17000},
    },
    "crm_lookup": {
        "acme": {"customer": "Acme Corp", "account_manager": "Sarah Johnson", "email": "sarah@company.com", "tier": "enterprise"},
    },
    "send_email": {"status": "sent", "message_id": "msg-12345"},
    "check_calendar": {"available": True, "next_slot": "Tuesday 2:00 PM"},
    "create_ticket": {"ticket_id": "TKT-789", "status": "open"},
}

# --- Tasks for the agent ---
TASKS = [
    {
        "id": "task-001",
        "description": "Find Q3 revenue and compare to target",
        "input": "What was our Q3 revenue and how does it compare to the target?",
        "expected_tools": ["sql_query", "vector_search", "calculator"],
        "max_steps": 4,
        "golden_trajectory": [
            {"thought": "Need Q3 actual revenue from database", "tool": "sql_query", "args": {"query": "SELECT revenue FROM quarterly WHERE quarter='Q3'"}, "result_key": "revenue_q3"},
            {"thought": "Need Q3 target from planning docs", "tool": "vector_search", "args": {"query": "Q3 2024 revenue target"}, "result_key": "revenue_target"},
            {"thought": "Calculate percentage above/below target", "tool": "calculator", "args": {"expression": "(2300000-2000000)/2000000*100"}, "result_key": "percentage"},
        ],
        "expected_output": "Q3 revenue was $2.3M, exceeding the $2.0M target by 15%."
    },
    {
        "id": "task-002",
        "description": "Find overdue invoices for Acme and notify account manager",
        "input": "Find all overdue invoices for Acme Corp and email a summary to their account manager.",
        "expected_tools": ["sql_query", "crm_lookup", "send_email"],
        "max_steps": 4,
        "golden_trajectory": [
            {"thought": "Query overdue invoices for Acme", "tool": "sql_query", "args": {"query": "SELECT * FROM invoices WHERE customer='Acme' AND status='overdue'"}, "result_key": "overdue_invoices"},
            {"thought": "Look up Acme's account manager", "tool": "crm_lookup", "args": {"customer": "Acme Corp"}, "result_key": "acme"},
            {"thought": "Send summary email to account manager", "tool": "send_email", "args": {"to": "sarah@company.com", "subject": "Overdue: Acme Corp"}, "result_key": None},
        ],
        "expected_output": "Found 2 overdue invoices for Acme Corp totaling $17,000. Summary sent to Sarah Johnson."
    },
    {
        "id": "task-003",
        "description": "Check enterprise customer count",
        "input": "How many enterprise customers do we have?",
        "expected_tools": ["sql_query"],
        "max_steps": 2,
        "golden_trajectory": [
            {"thought": "Query customer database for enterprise tier count", "tool": "sql_query", "args": {"query": "SELECT COUNT(*) FROM customers WHERE tier='enterprise'"}, "result_key": "customer_count"},
        ],
        "expected_output": "We have 45 enterprise customers."
    },
    {
        "id": "task-004",
        "description": "Schedule a meeting and create a follow-up ticket",
        "input": "Check if Tuesday at 2pm is available, and if so, create a support ticket for the meeting prep.",
        "expected_tools": ["check_calendar", "create_ticket"],
        "max_steps": 3,
        "golden_trajectory": [
            {"thought": "Check calendar availability for Tuesday 2pm", "tool": "check_calendar", "args": {"date": "Tuesday", "time": "14:00"}, "result_key": None},
            {"thought": "Tuesday 2pm is available, create prep ticket", "tool": "create_ticket", "args": {"title": "Meeting prep", "priority": "medium"}, "result_key": None},
        ],
        "expected_output": "Tuesday 2:00 PM is available. Created ticket TKT-789 for meeting prep."
    },
    {
        "id": "task-005",
        "description": "Look up refund policy details",
        "input": "What's the refund policy for enterprise customers?",
        "expected_tools": ["vector_search"],
        "max_steps": 2,
        "golden_trajectory": [
            {"thought": "Search for enterprise refund policy in docs", "tool": "vector_search", "args": {"query": "enterprise refund policy"}, "result_key": "refund_policy"},
        ],
        "expected_output": "Enterprise customers get a full refund within 60 days. After 60 days, prorated refund with 10% early termination fee."
    },
]


def simulate_agent_execution(task: dict) -> dict:
    """Use LLM to simulate an agent executing a task, recording trajectory."""
    tools_desc = "\n".join(f"- {name}: {desc}" for name, desc in AVAILABLE_TOOLS.items())
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"""You are an AI agent that completes tasks by calling tools.
Available tools:
{tools_desc}

For the given task, plan and execute step by step.
Return your trajectory as JSON array of steps:
[{{"thought": "why this step", "tool": "tool_name", "args": {{"key": "value"}}}}]

Be efficient - use minimum necessary tools. Return ONLY the JSON array."""},
            {"role": "user", "content": f"Task: {task['input']}"}
        ],
        temperature=0.3
    )
    
    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    
    try:
        steps = json.loads(text)
    except json.JSONDecodeError:
        steps = [{"thought": "Failed to parse", "tool": "error", "args": {}}]
    
    # Simulate tool results
    recorded_steps = []
    for i, step in enumerate(steps):
        tool = step.get("tool", "unknown")
        # Find a matching result
        result = None
        if tool in TOOL_RESULTS:
            if isinstance(TOOL_RESULTS[tool], dict):
                # Get first available result for this tool
                results_for_tool = TOOL_RESULTS[tool]
                if isinstance(list(results_for_tool.values())[0], dict) and "rows" not in list(results_for_tool.values())[0] or True:
                    result = list(results_for_tool.values())[0] if results_for_tool else {"status": "ok"}
            else:
                result = TOOL_RESULTS[tool]
        
        recorded_steps.append({
            "step": i + 1,
            "thought": step.get("thought", ""),
            "tool": tool,
            "args": step.get("args", {}),
            "result": result or {"status": "completed"},
            "latency_ms": int(50 + 200 * (0.5 + 0.5 * (i / max(len(steps), 1))))
        })
    
    return {
        "task_id": task["id"],
        "steps": recorded_steps,
        "total_steps": len(recorded_steps),
        "total_latency_ms": sum(s["latency_ms"] for s in recorded_steps)
    }


def compare_trajectories(agent_traj: list, golden_traj: list) -> dict:
    """Compare agent trajectory against golden trajectory."""
    golden_tools = [s["tool"] for s in golden_traj]
    agent_tools = [s["tool"] for s in agent_traj]
    
    # Tool sequence match
    tool_match = golden_tools == agent_tools[:len(golden_tools)]
    
    # Step efficiency
    efficiency = len(golden_traj) / max(len(agent_traj), 1)
    efficiency = min(efficiency, 1.0)
    
    # Tool coverage (did agent use all required tools?)
    required_set = set(golden_tools)
    agent_set = set(agent_tools)
    coverage = len(required_set & agent_set) / max(len(required_set), 1)
    
    # Extra tools (penalty for unnecessary tools)
    extra_tools = agent_set - required_set
    
    return {
        "tool_sequence_match": tool_match,
        "step_efficiency": round(efficiency, 2),
        "tool_coverage": round(coverage, 2),
        "extra_tools": list(extra_tools),
        "golden_steps": len(golden_traj),
        "agent_steps": len(agent_traj),
        "combined_score": round((efficiency + coverage + (1.0 if tool_match else 0.5)) / 3, 2)
    }


def main():
    print("=" * 70)
    print("TRAJECTORY RECORDER")
    print("=" * 70)
    print(f"\nTasks to execute: {len(TASKS)}")
    print(f"Available tools: {len(AVAILABLE_TOOLS)}")
    print("-" * 70)
    
    golden_trajectories = {
        "metadata": {
            "name": "agent-golden-trajectories",
            "version": "1.0.0",
            "created_at": datetime.now().isoformat(),
            "total_tasks": len(TASKS),
            "approved": 0,
            "rejected": 0
        },
        "trajectories": []
    }
    
    all_comparisons = []
    
    for task in TASKS:
        print(f"\n{'─' * 70}")
        print(f"TASK: {task['description']}")
        print(f"Input: {task['input']}")
        print(f"Expected tools: {task['expected_tools']}")
        print(f"{'─' * 70}")
        
        # Execute agent
        print("\n  🤖 Agent executing...")
        execution = simulate_agent_execution(task)
        
        # Display agent trajectory
        print(f"\n  Agent trajectory ({execution['total_steps']} steps):")
        for step in execution["steps"]:
            print(f"    Step {step['step']}: [{step['tool']}] {step['thought'][:60]}")
        
        # Display golden trajectory
        print(f"\n  Golden trajectory ({len(task['golden_trajectory'])} steps):")
        for i, step in enumerate(task["golden_trajectory"]):
            print(f"    Step {i+1}: [{step['tool']}] {step['thought'][:60]}")
        
        # Compare
        comparison = compare_trajectories(execution["steps"], task["golden_trajectory"])
        all_comparisons.append(comparison)
        
        print(f"\n  📊 Comparison:")
        print(f"    Tool sequence match: {'✓' if comparison['tool_sequence_match'] else '✗'}")
        print(f"    Step efficiency:     {comparison['step_efficiency']:.0%} (golden: {comparison['golden_steps']}, agent: {comparison['agent_steps']})")
        print(f"    Tool coverage:       {comparison['tool_coverage']:.0%}")
        print(f"    Extra tools used:    {comparison['extra_tools'] or 'none'}")
        print(f"    Combined score:      {comparison['combined_score']:.2f}")
        
        # Approval decision (auto-approve if score > 0.7)
        approved = comparison["combined_score"] >= 0.7
        status = "APPROVED ✓" if approved else "REJECTED ✗"
        print(f"\n  Decision: {status}")
        
        if approved:
            golden_trajectories["metadata"]["approved"] += 1
        else:
            golden_trajectories["metadata"]["rejected"] += 1
        
        # Add to golden trajectories (mark status)
        trajectory_record = {
            "id": f"traj-{uuid.uuid4().hex[:8]}",
            "task_id": task["id"],
            "task_description": task["description"],
            "input": task["input"],
            "golden_steps": task["golden_trajectory"],
            "agent_steps": execution["steps"],
            "expected_output": task["expected_output"],
            "comparison": comparison,
            "status": "golden" if approved else "rejected",
            "max_steps": task["max_steps"],
            "required_tools": task["expected_tools"],
            "recorded_at": datetime.now().isoformat()
        }
        golden_trajectories["trajectories"].append(trajectory_record)
    
    # Save
    output_path = "golden_trajectories.json"
    with open(output_path, "w") as f:
        json.dump(golden_trajectories, f, indent=2)
    
    # Summary
    print(f"\n{'=' * 70}")
    print("TRAJECTORY RECORDING SUMMARY")
    print("=" * 70)
    
    approved = golden_trajectories["metadata"]["approved"]
    rejected = golden_trajectories["metadata"]["rejected"]
    total = approved + rejected
    
    print(f"\n  Total tasks:    {total}")
    print(f"  Approved:       {approved} ({approved/total*100:.0f}%)")
    print(f"  Rejected:       {rejected} ({rejected/total*100:.0f}%)")
    
    avg_efficiency = sum(c["step_efficiency"] for c in all_comparisons) / len(all_comparisons)
    avg_coverage = sum(c["tool_coverage"] for c in all_comparisons) / len(all_comparisons)
    avg_score = sum(c["combined_score"] for c in all_comparisons) / len(all_comparisons)
    
    print(f"\n  Avg efficiency: {avg_efficiency:.0%}")
    print(f"  Avg coverage:   {avg_coverage:.0%}")
    print(f"  Avg score:      {avg_score:.2f}")
    
    print(f"\n  Output: {output_path}")
    print(f"  Golden trajectories ready for agent evaluation!")
    print("=" * 70)


if __name__ == "__main__":
    main()
