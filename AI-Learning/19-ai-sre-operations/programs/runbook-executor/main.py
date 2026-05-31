"""
Runbook Executor for AI Incidents
Simulates step-by-step runbook execution for common AI incident types.
"""

import time
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


class StepType(Enum):
    AUTOMATED = "AUTO"
    MANUAL = "MANUAL"
    DECISION = "DECISION"
    CHECK = "CHECK"


class StepStatus(Enum):
    SUCCESS = "✓"
    FAILED = "✗"
    SKIPPED = "→"
    WARNING = "⚠"


@dataclass
class RunbookStep:
    name: str
    step_type: StepType
    description: str
    duration_sec: int
    status: StepStatus = None
    output: str = ""
    decision_taken: str = ""


@dataclass
class IncidentResponse:
    incident_type: str
    severity: str
    started: datetime
    steps: list = field(default_factory=list)
    resolved: datetime = None
    resolution_summary: str = ""


class RunbookExecutor:
    """Simulates execution of AI incident runbooks."""

    def __init__(self):
        self.current_time = datetime(2024, 12, 15, 14, 23, 0)
        self.responses: list[IncidentResponse] = []

    def run_all_runbooks(self):
        """Execute all runbook simulations."""
        print("=" * 70)
        print("  AI INCIDENT RUNBOOK EXECUTION SIMULATOR")
        print("=" * 70)
        print()
        print("  Simulating real-time runbook execution for 3 incident types.")
        print("  Each step shows: type (AUTO/MANUAL/CHECK/DECISION), action, and result.")
        print()

        self.execute_provider_outage()
        print()
        self.execute_hallucination_spike()
        print()
        self.execute_cost_runaway()

        self._print_summary()

    def execute_provider_outage(self):
        """Runbook: Provider Outage with Failover."""
        response = IncidentResponse(
            incident_type="Provider Outage",
            severity="P1",
            started=self.current_time,
        )

        self._print_header("PROVIDER OUTAGE", "P1",
                          "Alert: provider_error_rate > 95% for 2 minutes")

        steps = [
            # First Response
            RunbookStep("Acknowledge alert", StepType.MANUAL,
                       "On-call acknowledges and opens incident channel", 30),
            RunbookStep("Verify outage", StepType.AUTOMATED,
                       "Health check: POST /v1/chat/completions → timeout", 10),
            RunbookStep("Check provider status", StepType.CHECK,
                       "status.openai.com → 'Investigating increased errors'", 20),
            RunbookStep("Assess scope", StepType.CHECK,
                       "All models affected, not just one endpoint", 15),

            # Mitigation
            RunbookStep("Trigger failover", StepType.AUTOMATED,
                       "Route traffic to Azure OpenAI (secondary provider)", 5),
            RunbookStep("Verify failover health", StepType.AUTOMATED,
                       "Secondary provider responding, latency +200ms, quality 0.89", 15),
            RunbookStep("Check error rate post-failover", StepType.CHECK,
                       "Error rate: 0.5% (acceptable, was 95%)", 30),
            RunbookStep("Communicate status", StepType.MANUAL,
                       "Post: 'Failover active, service restored on secondary'", 60),

            # Monitoring
            RunbookStep("Monitor secondary stability", StepType.AUTOMATED,
                       "5-min check: latency stable, quality stable, cost +15%", 300),
            RunbookStep("Monitor primary recovery", StepType.AUTOMATED,
                       "Health checks polling primary every 60s", 600),

            # Recovery
            RunbookStep("Primary recovered", StepType.CHECK,
                       "5 consecutive health checks passed on primary", 10),
            RunbookStep("Canary traffic to primary", StepType.AUTOMATED,
                       "Route 10% traffic to primary, monitor for 5 min", 300),
            RunbookStep("Verify primary quality", StepType.CHECK,
                       "Primary quality score: 0.93 (normal), latency: 180ms", 15),
            RunbookStep("Full traffic restore", StepType.DECISION,
                       "Decision: restore 100% to primary (quality confirmed)",  5),
            RunbookStep("Confirm resolution", StepType.CHECK,
                       "All metrics normal for 15 minutes", 900),
        ]

        self._execute_steps(response, steps)
        response.resolution_summary = (
            "Provider outage lasted 22 minutes. Auto-failover activated in 5s. "
            "User impact: ~200ms additional latency during failover. "
            "Quality maintained above 0.88 throughout."
        )
        response.resolved = self.current_time
        self.responses.append(response)

        self._print_resolution(response)

    def execute_hallucination_spike(self):
        """Runbook: Hallucination Rate Spike."""
        self.current_time = datetime(2024, 12, 15, 16, 45, 0)

        response = IncidentResponse(
            incident_type="Hallucination Spike",
            severity="P1",
            started=self.current_time,
        )

        self._print_header("HALLUCINATION SPIKE", "P1",
                          "Alert: hallucination_rate > 12% for 10 minutes (SLO: <5%)")

        steps = [
            # First Response
            RunbookStep("Acknowledge alert", StepType.MANUAL,
                       "On-call acknowledges, escalates to ML on-call", 60),
            RunbookStep("Verify spike", StepType.CHECK,
                       "Sample 10 flagged responses: 8/10 confirmed hallucinations", 180),
            RunbookStep("Tighten guardrails", StepType.AUTOMATED,
                       "Lower confidence threshold from 0.8 to 0.6 (blocks more)", 10),
            RunbookStep("Communicate", StepType.MANUAL,
                       "Post: 'Investigating quality issue, guardrails tightened'", 30),

            # Diagnosis
            RunbookStep("Check retrieval quality", StepType.CHECK,
                       "Run 20 test queries → recall@10 dropped from 0.85 to 0.62", 120),
            RunbookStep("Check vector DB health", StepType.CHECK,
                       "Cluster healthy, all nodes up, latency normal", 30),
            RunbookStep("Check embedding freshness", StepType.CHECK,
                       "Last embedding job: 3 hours ago — completed with errors!", 60),
            RunbookStep("Identify root cause", StepType.DECISION,
                       "Decision: embedding job partially failed, 40% of vectors are stale/corrupted", 120),

            # Resolution
            RunbookStep("Roll back corrupted vectors", StepType.AUTOMATED,
                       "Restore vector DB snapshot from before failed job", 180),
            RunbookStep("Verify retrieval quality", StepType.CHECK,
                       "Recall@10 restored to 0.84", 60),
            RunbookStep("Test hallucination rate", StepType.AUTOMATED,
                       "Run eval on 100 queries: hallucination rate 3.2%", 120),
            RunbookStep("Relax guardrails", StepType.DECISION,
                       "Decision: raise threshold back to 0.75 (not 0.8 yet, monitoring)", 10),
            RunbookStep("Fix embedding pipeline", StepType.MANUAL,
                       "Add error handling: if >5% chunks fail, abort and alert", 600),
            RunbookStep("Re-run embedding job", StepType.AUTOMATED,
                       "Successful: all 100% chunks embedded correctly", 900),
            RunbookStep("Final verification", StepType.CHECK,
                       "24h monitor: hallucination rate stable at 2.8%", 60),
        ]

        self._execute_steps(response, steps)
        response.resolution_summary = (
            "Root cause: embedding pipeline job partially failed, corrupting 40% of vectors. "
            "Vector DB restored from snapshot, pipeline fixed with error handling. "
            "Total incident duration: 42 minutes detection-to-mitigation, 2 hours to full resolution. "
            "~150 users received hallucinated responses before guardrails activated."
        )
        response.resolved = self.current_time
        self.responses.append(response)

        self._print_resolution(response)

    def execute_cost_runaway(self):
        """Runbook: Cost Runaway from Agent Loop."""
        self.current_time = datetime(2024, 12, 16, 3, 15, 0)

        response = IncidentResponse(
            incident_type="Cost Runaway",
            severity="P2",
            started=self.current_time,
        )

        self._print_header("COST RUNAWAY", "P2",
                          "Alert: hourly_cost $420 (3x baseline of $140)")

        steps = [
            # First Response
            RunbookStep("Acknowledge alert", StepType.MANUAL,
                       "On-call acknowledges (paged at 3:15 AM)", 120),
            RunbookStep("Check cost dashboard", StepType.CHECK,
                       "Top consumer: agent-research endpoint (78% of spend)", 30),
            RunbookStep("Identify specific agents", StepType.CHECK,
                       "3 agent instances running >45 min each, 120K+ tokens each", 60),

            # Mitigation
            RunbookStep("Kill runaway agents", StepType.AUTOMATED,
                       "Terminated 3 agents: agent-7x92k, agent-3f81m, agent-9k22p", 5),
            RunbookStep("Verify cost drop", StepType.CHECK,
                       "Hourly cost projection dropped to $95 (below baseline)", 60),
            RunbookStep("Check for more runaways", StepType.AUTOMATED,
                       "Scan all active agents: no others exceeding limits", 30),

            # Diagnosis
            RunbookStep("Investigate agent behavior", StepType.CHECK,
                       "All 3 were researching same topic, hitting dead-end tool calls", 180),
            RunbookStep("Identify trigger", StepType.CHECK,
                       "User query triggered parallel agents, tool returned ambiguous errors", 120),
            RunbookStep("Root cause analysis", StepType.DECISION,
                       "Decision: agent retry logic doesn't distinguish 'error' from 'no result'", 60),

            # Resolution
            RunbookStep("Implement agent token budget", StepType.AUTOMATED,
                       "Set max_tokens_per_agent = 50,000, max_iterations = 30", 30),
            RunbookStep("Fix retry logic", StepType.MANUAL,
                       "Add: if tool returns error 3x consecutively, stop and report", 300),
            RunbookStep("Calculate total overspend", StepType.CHECK,
                       "Extra cost: $840 over 3 hours (agents ran from midnight)", 30),
            RunbookStep("Verify fix", StepType.AUTOMATED,
                       "Test: trigger same query — agent stops after 28 iterations, $1.20 cost", 60),
        ]

        self._execute_steps(response, steps)
        response.resolution_summary = (
            "Root cause: 3 research agents stuck in retry loop due to ambiguous tool errors. "
            "Ran for 3+ hours before cost alert fired. Total overspend: $840. "
            "Fix: agent token budgets (50K max) and retry logic improvement. "
            "Prevention: per-agent cost limit + max iteration count."
        )
        response.resolved = self.current_time
        self.responses.append(response)

        self._print_resolution(response)

    def _execute_steps(self, response: IncidentResponse, steps: list[RunbookStep]):
        """Execute and display each step."""
        for i, step in enumerate(steps, 1):
            # Simulate execution
            self.current_time += timedelta(seconds=step.duration_sec)

            # Determine status (simulate realistic outcomes)
            if step.step_type == StepType.DECISION:
                step.status = StepStatus.SUCCESS
                step.decision_taken = step.description.split("Decision: ")[-1] if "Decision:" in step.description else step.description
            elif step.step_type == StepType.CHECK:
                step.status = StepStatus.SUCCESS
            elif step.step_type == StepType.AUTOMATED:
                step.status = StepStatus.SUCCESS
            else:
                step.status = StepStatus.SUCCESS

            response.steps.append(step)

            # Display
            elapsed = (self.current_time - response.started).total_seconds()
            elapsed_str = f"+{int(elapsed//60):02d}:{int(elapsed%60):02d}"

            type_str = f"[{step.step_type.value:>8}]"
            status_str = step.status.value

            print(f"    {elapsed_str} {status_str} {type_str} {step.name}")
            print(f"           └─ {step.description}")

    def _print_header(self, title: str, severity: str, trigger: str):
        """Print runbook execution header."""
        print(f"  {'━' * 66}")
        print(f"  ┃ RUNBOOK EXECUTION: {title}")
        print(f"  ┃ Severity: {severity}")
        print(f"  ┃ Trigger:  {trigger}")
        print(f"  ┃ Started:  {self.current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  {'━' * 66}")
        print()

    def _print_resolution(self, response: IncidentResponse):
        """Print resolution summary."""
        duration = (response.resolved - response.started).total_seconds()
        auto_steps = sum(1 for s in response.steps if s.step_type == StepType.AUTOMATED)
        manual_steps = sum(1 for s in response.steps if s.step_type == StepType.MANUAL)
        check_steps = sum(1 for s in response.steps if s.step_type == StepType.CHECK)
        decision_steps = sum(1 for s in response.steps if s.step_type == StepType.DECISION)

        print()
        print(f"  ┃ RESOLVED: {response.resolved.strftime('%H:%M:%S')}")
        print(f"  ┃ Duration: {int(duration//60)} minutes")
        print(f"  ┃ Steps: {len(response.steps)} total "
              f"({auto_steps} auto, {manual_steps} manual, {check_steps} checks, {decision_steps} decisions)")
        print(f"  ┃")
        print(f"  ┃ Summary: {response.resolution_summary}")
        print(f"  {'━' * 66}")

    def _print_summary(self):
        """Print overall summary of all runbook executions."""
        print()
        print("=" * 70)
        print("  RUNBOOK EXECUTION SUMMARY")
        print("=" * 70)
        print()

        total_steps = 0
        total_auto = 0
        total_manual = 0

        for response in self.responses:
            duration = (response.resolved - response.started).total_seconds()
            auto = sum(1 for s in response.steps if s.step_type == StepType.AUTOMATED)
            manual = sum(1 for s in response.steps if s.step_type in (StepType.MANUAL, StepType.DECISION))
            total_steps += len(response.steps)
            total_auto += auto
            total_manual += manual

            print(f"  {response.incident_type:<25} | {response.severity} | "
                  f"{int(duration//60):>3} min | "
                  f"{len(response.steps)} steps ({auto} auto, {manual} manual)")

        print()
        print(f"  {'─' * 60}")
        print(f"  Automation rate: {total_auto/total_steps:.0%} of steps were automated")
        print(f"  Human decisions: {total_manual} steps required human judgment")
        print()
        print("  KEY INSIGHTS:")
        print("    1. Provider failover is almost fully automatable (90%+ auto)")
        print("    2. Quality issues require human diagnosis (ML expertise needed)")
        print("    3. Cost runaways need immediate kill + root cause analysis")
        print("    4. Detection-to-mitigation should be < 5 min for P1 incidents")
        print("    5. Full resolution often takes longer — mitigation buys time")
        print()
        print("=" * 70)


if __name__ == "__main__":
    executor = RunbookExecutor()
    executor.run_all_runbooks()
