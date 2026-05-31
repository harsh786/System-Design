"""
Multi-Agent System: Supervisor + Specialists
=============================================
A supervisor agent delegates work to Researcher, Analyzer, and Writer agents.
Demonstrates inter-agent communication and task orchestration.
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =============================================================================
# SPECIALIST AGENTS
# =============================================================================

class SpecialistAgent:
    """Base class for specialist agents."""

    def __init__(self, name: str, system_prompt: str, tools: dict = None):
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools or {}

    def run(self, task: str, context: str = "") -> str:
        """Execute a task with optional context from other agents."""
        print(f"\n  🤖 [{self.name}] Working on: {task[:80]}...")

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Task: {task}\n\nContext from other agents:\n{context}" if context else f"Task: {task}"},
        ]

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.3,
            max_tokens=600,
        )

        result = response.choices[0].message.content
        print(f"  ✅ [{self.name}] Done ({len(result)} chars)")
        return result


# Create specialist agents
researcher = SpecialistAgent(
    name="Researcher",
    system_prompt="""You are a Research Specialist. Your job is to gather and organize information.

When given a research task:
1. Identify key areas to investigate
2. Provide factual, data-driven findings
3. Organize information clearly with bullet points
4. Note any gaps or uncertainties
5. Cite sources where possible (you can simulate this)

Be thorough but concise. Focus on facts, not opinions."""
)

analyzer = SpecialistAgent(
    name="Analyzer",
    system_prompt="""You are an Analysis Specialist. Your job is to analyze data and extract insights.

When given data/research to analyze:
1. Identify key trends and patterns
2. Compare and contrast options
3. Highlight risks and opportunities
4. Provide quantitative assessments where possible
5. Draw actionable conclusions

Be analytical and objective. Support conclusions with evidence from the research provided."""
)

writer = SpecialistAgent(
    name="Writer",
    system_prompt="""You are a Writing Specialist. Your job is to produce polished, professional reports.

When given research and analysis:
1. Structure the content with clear sections
2. Write an executive summary
3. Present findings clearly and persuasively
4. Include recommendations
5. Use professional but accessible language

Produce a complete, ready-to-present document. Use markdown formatting."""
)

SPECIALISTS = {
    "researcher": researcher,
    "analyzer": analyzer,
    "writer": writer,
}

# =============================================================================
# SUPERVISOR AGENT
# =============================================================================

SUPERVISOR_PROMPT = """You are a Supervisor Agent managing a team of three specialists:

1. **Researcher** - Gathers information, finds data, investigates topics
2. **Analyzer** - Analyzes data, identifies patterns, compares options, draws conclusions
3. **Writer** - Produces polished reports, summaries, and documents

Your job is to:
1. Break the task into sub-tasks for your team
2. Decide which agent to call and in what order
3. Pass context between agents (research → analysis → writing)
4. Ensure quality of final output

Respond with a JSON object specifying the next action:
{
    "next_agent": "researcher|analyzer|writer|done",
    "task_for_agent": "specific instructions for the agent",
    "reasoning": "why you're choosing this agent next"
}

When all work is complete, use "done" as next_agent and include the final status.
Output ONLY valid JSON."""


def run_supervisor(task: str, max_delegations: int = 6):
    """Run the supervisor-worker multi-agent system."""
    print("=" * 60)
    print(f"🎯 TASK: {task}")
    print("=" * 60)
    print("\n👔 SUPERVISOR: Analyzing task and delegating work...\n")

    # Shared state between agents
    shared_state = {
        "task": task,
        "research": None,
        "analysis": None,
        "report": None,
    }

    supervisor_messages = [
        {"role": "system", "content": SUPERVISOR_PROMPT},
        {"role": "user", "content": f"Task to complete: {task}\n\nCurrent state: Nothing done yet. Start by deciding which agent should work first."},
    ]

    for i in range(max_delegations):
        print(f"\n{'─' * 40}")
        print(f"  DELEGATION {i + 1}")
        print(f"{'─' * 40}")

        # Supervisor decides next action
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=supervisor_messages,
            temperature=0,
            response_format={"type": "json_object"},
        )

        decision = json.loads(response.choices[0].message.content)
        next_agent = decision.get("next_agent", "done")
        agent_task = decision.get("task_for_agent", "")
        reasoning = decision.get("reasoning", "")

        print(f"  👔 Supervisor decides: → {next_agent}")
        print(f"     Reasoning: {reasoning}")

        # Check if done
        if next_agent == "done":
            print(f"\n{'=' * 60}")
            print("✅ SUPERVISOR: All work complete!")
            print(f"{'=' * 60}")
            break

        # Delegate to specialist
        if next_agent in SPECIALISTS:
            # Build context from shared state
            context_parts = []
            if shared_state["research"]:
                context_parts.append(f"Research findings:\n{shared_state['research']}")
            if shared_state["analysis"]:
                context_parts.append(f"Analysis:\n{shared_state['analysis']}")
            context = "\n\n".join(context_parts)

            # Run the specialist
            result = SPECIALISTS[next_agent].run(agent_task, context)

            # Store result in shared state
            if next_agent == "researcher":
                shared_state["research"] = result
            elif next_agent == "analyzer":
                shared_state["analysis"] = result
            elif next_agent == "writer":
                shared_state["report"] = result

            # Update supervisor with result
            supervisor_messages.append({"role": "assistant", "content": json.dumps(decision)})
            supervisor_messages.append({
                "role": "user",
                "content": f"Agent '{next_agent}' completed their task.\n\nResult summary: {result[:300]}...\n\nCurrent state:\n- Research: {'Done' if shared_state['research'] else 'Pending'}\n- Analysis: {'Done' if shared_state['analysis'] else 'Pending'}\n- Report: {'Done' if shared_state['report'] else 'Pending'}\n\nWhat should happen next?",
            })
        else:
            print(f"  ❌ Unknown agent: {next_agent}")
            break

    # Print final report
    if shared_state["report"]:
        print(f"\n{'━' * 60}")
        print("📄 FINAL REPORT")
        print(f"{'━' * 60}")
        print(shared_state["report"])

    return shared_state


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    task = """Create a market analysis report for an AI-powered code review tool targeting 
    enterprise software teams. Research the competitive landscape (existing tools like 
    CodeRabbit, Codacy, SonarQube), analyze market opportunities and risks, and produce 
    a professional report with recommendations for a startup entering this market."""

    result = run_supervisor(task)
