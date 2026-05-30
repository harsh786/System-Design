"""
AI SRE - Automated Runbook System
==================================
Defines and executes operational runbooks for AI system incidents.
Includes pre-flight checks, step-by-step execution, rollback, and audit logging.
"""

import time
import json
import uuid
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
from collections import defaultdict
import threading
import traceback

logger = logging.getLogger(__name__)


# =============================================================================
# RUNBOOK DEFINITION SCHEMA
# =============================================================================

class RunbookSeverity(Enum):
    CRITICAL = "critical"  # Immediate execution, minimal confirmation
    HIGH = "high"          # Quick execution, single confirmation
    MEDIUM = "medium"      # Standard execution, step-by-step confirmation
    LOW = "low"            # Careful execution, full review before each step


class RunbookStatus(Enum):
    PENDING = "pending"
    PREFLIGHT = "preflight"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"


@dataclass
class RunbookStep:
    """A single step in a runbook."""
    id: str
    name: str
    description: str
    action: Callable  # Function to execute
    rollback_action: Optional[Callable] = None  # Undo function
    pre_check: Optional[Callable] = None  # Verify preconditions
    post_check: Optional[Callable] = None  # Verify success
    timeout_seconds: int = 300
    requires_confirmation: bool = False
    can_skip: bool = False
    retry_count: int = 0
    retry_delay_seconds: int = 5
    
    # Runtime state
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None


@dataclass
class PreflightCheck:
    """A safety check that must pass before runbook execution."""
    name: str
    description: str
    check_fn: Callable[[], bool]
    severity: str = "blocking"  # "blocking" or "warning"
    
    passed: Optional[bool] = None
    message: str = ""


@dataclass
class RunbookDefinition:
    """Complete runbook definition."""
    id: str
    name: str
    description: str
    severity: RunbookSeverity
    trigger_conditions: list[str]  # What triggers this runbook
    
    # Steps
    preflight_checks: list[PreflightCheck] = field(default_factory=list)
    steps: list[RunbookStep] = field(default_factory=list)
    
    # Metadata
    owner: str = ""
    team: str = ""
    estimated_duration_minutes: int = 5
    last_executed: Optional[datetime] = None
    last_tested: Optional[datetime] = None
    version: str = "1.0.0"
    
    # Policy
    requires_approval: bool = False
    max_concurrent_executions: int = 1
    cooldown_minutes: int = 15


@dataclass
class RunbookExecution:
    """A single execution of a runbook."""
    id: str
    runbook_id: str
    status: RunbookStatus
    triggered_by: str  # "alert", "manual", "automation"
    trigger_context: dict  # Context from the trigger
    
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    preflight_results: list[dict] = field(default_factory=list)
    step_results: list[dict] = field(default_factory=list)
    
    # Audit
    executor: str = ""  # Who/what executed this
    approval_by: Optional[str] = None
    notes: list[str] = field(default_factory=list)


# =============================================================================
# RUNBOOK EXECUTION ENGINE
# =============================================================================

class RunbookExecutionEngine:
    """Executes runbooks with safety controls, logging, and rollback."""
    
    def __init__(self):
        self._runbooks: dict[str, RunbookDefinition] = {}
        self._executions: list[RunbookExecution] = []
        self._active_executions: dict[str, RunbookExecution] = {}
        self._lock = threading.Lock()
        self._confirmation_callback: Optional[Callable[[str, str], bool]] = None
    
    def register_runbook(self, runbook: RunbookDefinition):
        """Register a runbook definition."""
        self._runbooks[runbook.id] = runbook
        logger.info(f"Registered runbook: {runbook.id} ({runbook.name})")
    
    def set_confirmation_callback(self, callback: Callable[[str, str], bool]):
        """Set callback for step confirmations (returns True to proceed)."""
        self._confirmation_callback = callback
    
    def execute(self, runbook_id: str, trigger_context: dict,
                triggered_by: str = "automation", executor: str = "system") -> RunbookExecution:
        """Execute a runbook."""
        runbook = self._runbooks.get(runbook_id)
        if not runbook:
            raise ValueError(f"Unknown runbook: {runbook_id}")
        
        # Check cooldown
        if runbook.last_executed:
            cooldown_end = runbook.last_executed + timedelta(minutes=runbook.cooldown_minutes)
            if datetime.utcnow() < cooldown_end:
                raise RuntimeError(
                    f"Runbook {runbook_id} in cooldown until {cooldown_end.isoformat()}"
                )
        
        # Check concurrent executions
        with self._lock:
            active_count = sum(1 for e in self._active_executions.values() 
                             if e.runbook_id == runbook_id)
            if active_count >= runbook.max_concurrent_executions:
                raise RuntimeError(
                    f"Runbook {runbook_id} max concurrent executions reached ({active_count})"
                )
        
        # Create execution record
        execution = RunbookExecution(
            id=str(uuid.uuid4()),
            runbook_id=runbook_id,
            status=RunbookStatus.PENDING,
            triggered_by=triggered_by,
            trigger_context=trigger_context,
            executor=executor,
        )
        
        self._active_executions[execution.id] = execution
        
        try:
            # Phase 1: Preflight checks
            execution.status = RunbookStatus.PREFLIGHT
            if not self._run_preflight_checks(runbook, execution):
                execution.status = RunbookStatus.FAILED
                execution.completed_at = datetime.utcnow()
                execution.notes.append("Failed preflight checks")
                return execution
            
            # Phase 2: Execute steps
            execution.status = RunbookStatus.RUNNING
            success = self._execute_steps(runbook, execution)
            
            if success:
                execution.status = RunbookStatus.COMPLETED
                execution.notes.append("All steps completed successfully")
            else:
                # Phase 3: Rollback on failure
                execution.notes.append("Execution failed, initiating rollback")
                self._rollback(runbook, execution)
                execution.status = RunbookStatus.ROLLED_BACK
            
        except Exception as e:
            execution.status = RunbookStatus.FAILED
            execution.notes.append(f"Unexpected error: {str(e)}")
            logger.error(f"Runbook {runbook_id} failed: {traceback.format_exc()}")
        finally:
            execution.completed_at = datetime.utcnow()
            runbook.last_executed = execution.completed_at
            del self._active_executions[execution.id]
            self._executions.append(execution)
        
        return execution
    
    def _run_preflight_checks(self, runbook: RunbookDefinition, 
                              execution: RunbookExecution) -> bool:
        """Run all preflight checks. Returns True if all blocking checks pass."""
        all_pass = True
        
        for check in runbook.preflight_checks:
            try:
                passed = check.check_fn()
                check.passed = passed
                result = {
                    "name": check.name,
                    "passed": passed,
                    "severity": check.severity,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                
                if not passed:
                    if check.severity == "blocking":
                        all_pass = False
                        result["message"] = f"BLOCKING: {check.description} - FAILED"
                        logger.error(f"Preflight BLOCKING check failed: {check.name}")
                    else:
                        result["message"] = f"WARNING: {check.description} - FAILED (non-blocking)"
                        logger.warning(f"Preflight WARNING check failed: {check.name}")
                else:
                    result["message"] = f"PASSED: {check.description}"
                
                execution.preflight_results.append(result)
                
            except Exception as e:
                execution.preflight_results.append({
                    "name": check.name,
                    "passed": False,
                    "severity": check.severity,
                    "message": f"CHECK ERROR: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat(),
                })
                if check.severity == "blocking":
                    all_pass = False
        
        return all_pass
    
    def _execute_steps(self, runbook: RunbookDefinition, 
                       execution: RunbookExecution) -> bool:
        """Execute runbook steps sequentially. Returns True if all succeed."""
        for step in runbook.steps:
            # Confirmation gate
            if step.requires_confirmation:
                if self._confirmation_callback:
                    approved = self._confirmation_callback(
                        f"Runbook '{runbook.name}'",
                        f"Proceed with step: {step.name}? ({step.description})"
                    )
                    if not approved:
                        step.status = StepStatus.SKIPPED
                        execution.step_results.append({
                            "step_id": step.id, "name": step.name,
                            "status": "skipped", "reason": "confirmation_denied",
                        })
                        if not step.can_skip:
                            return False
                        continue
            
            # Pre-check
            if step.pre_check:
                try:
                    pre_ok = step.pre_check()
                    if not pre_ok:
                        logger.warning(f"Pre-check failed for step: {step.name}")
                        if not step.can_skip:
                            step.status = StepStatus.FAILED
                            step.error = "Pre-check failed"
                            execution.step_results.append({
                                "step_id": step.id, "name": step.name,
                                "status": "failed", "reason": "pre_check_failed",
                            })
                            return False
                        step.status = StepStatus.SKIPPED
                        continue
                except Exception as e:
                    logger.error(f"Pre-check error for step {step.name}: {e}")
                    if not step.can_skip:
                        return False
                    continue
            
            # Execute with retries
            step.status = StepStatus.RUNNING
            step.started_at = datetime.utcnow()
            
            success = False
            attempts = step.retry_count + 1
            last_error = None
            
            for attempt in range(attempts):
                try:
                    step.result = step.action()
                    success = True
                    break
                except Exception as e:
                    last_error = str(e)
                    logger.warning(
                        f"Step '{step.name}' attempt {attempt + 1}/{attempts} failed: {e}"
                    )
                    if attempt < attempts - 1:
                        time.sleep(step.retry_delay_seconds)
            
            if success:
                step.status = StepStatus.COMPLETED
                step.completed_at = datetime.utcnow()
                
                # Post-check
                if step.post_check:
                    try:
                        post_ok = step.post_check()
                        if not post_ok:
                            logger.error(f"Post-check failed for step: {step.name}")
                            step.status = StepStatus.FAILED
                            step.error = "Post-check failed"
                            execution.step_results.append({
                                "step_id": step.id, "name": step.name,
                                "status": "failed", "reason": "post_check_failed",
                            })
                            return False
                    except Exception as e:
                        logger.error(f"Post-check error: {e}")
                
                execution.step_results.append({
                    "step_id": step.id, "name": step.name,
                    "status": "completed",
                    "duration_seconds": (step.completed_at - step.started_at).total_seconds(),
                    "result": str(step.result)[:500],
                })
            else:
                step.status = StepStatus.FAILED
                step.error = last_error
                step.completed_at = datetime.utcnow()
                execution.step_results.append({
                    "step_id": step.id, "name": step.name,
                    "status": "failed", "error": last_error,
                    "attempts": attempts,
                })
                return False
        
        return True
    
    def _rollback(self, runbook: RunbookDefinition, execution: RunbookExecution):
        """Rollback completed steps in reverse order."""
        completed_steps = [s for s in runbook.steps if s.status == StepStatus.COMPLETED]
        
        for step in reversed(completed_steps):
            if step.rollback_action:
                try:
                    logger.info(f"Rolling back step: {step.name}")
                    step.rollback_action()
                    step.status = StepStatus.ROLLED_BACK
                    execution.notes.append(f"Rolled back: {step.name}")
                except Exception as e:
                    logger.error(f"Rollback failed for step {step.name}: {e}")
                    execution.notes.append(f"ROLLBACK FAILED for {step.name}: {e}")


# =============================================================================
# SPECIFIC AI RUNBOOKS
# =============================================================================

class AIRunbookFactory:
    """Creates pre-defined runbooks for common AI incidents."""
    
    def __init__(self, config: dict = None):
        self._config = config or {}
        # Simulated system state
        self._state = {
            "active_model": "gpt-4",
            "fallback_model": "gpt-3.5-turbo",
            "active_prompt_version": "v2.3",
            "previous_prompt_version": "v2.2",
            "active_index": "index-v5",
            "previous_index": "index-v4",
            "max_agent_steps": 20,
            "human_approval_enabled": False,
            "write_actions_paused": False,
            "disabled_tools": [],
            "blocked_users": [],
            "disabled_mcp_servers": [],
        }
    
    def create_all_runbooks(self) -> list[RunbookDefinition]:
        """Create all standard AI runbooks."""
        return [
            self._create_disable_tools_runbook(),
            self._create_switch_provider_runbook(),
            self._create_rollback_prompt_runbook(),
            self._create_rollback_retriever_runbook(),
            self._create_disable_mcp_server_runbook(),
            self._create_block_user_runbook(),
            self._create_lower_max_steps_runbook(),
            self._create_force_human_approval_runbook(),
            self._create_pause_write_actions_runbook(),
            self._create_purge_documents_runbook(),
            self._create_reindex_knowledge_base_runbook(),
        ]
    
    def _create_disable_tools_runbook(self) -> RunbookDefinition:
        """Runbook: Disable a malfunctioning tool."""
        
        def check_tool_exists():
            # In production: verify tool is registered
            return True
        
        def identify_tool():
            logger.info("Identifying problematic tool from recent errors...")
            return {"tool_name": "database_query", "error_rate": 0.85}
        
        def disable_tool():
            tool_name = "database_query"  # Would come from context
            self._state["disabled_tools"].append(tool_name)
            logger.info(f"Disabled tool: {tool_name}")
            return f"Tool '{tool_name}' disabled"
        
        def verify_disabled():
            return "database_query" in self._state["disabled_tools"]
        
        def rollback_disable():
            if "database_query" in self._state["disabled_tools"]:
                self._state["disabled_tools"].remove("database_query")
        
        def notify_teams():
            logger.info("Notifying dependent teams about disabled tool")
            return "Notifications sent"
        
        return RunbookDefinition(
            id="disable_tools",
            name="Disable Malfunctioning Tool",
            description="Disable a tool that is causing errors, agent loops, or security issues",
            severity=RunbookSeverity.HIGH,
            trigger_conditions=["tool_error_rate > 50%", "tool_causing_agent_loop", "tool_security_issue"],
            preflight_checks=[
                PreflightCheck(
                    name="tool_registry_accessible",
                    description="Tool registry service is accessible",
                    check_fn=lambda: True,
                    severity="blocking",
                ),
                PreflightCheck(
                    name="fallback_behavior_defined",
                    description="Graceful degradation is configured for tool absence",
                    check_fn=lambda: True,
                    severity="warning",
                ),
            ],
            steps=[
                RunbookStep(id="identify", name="Identify Problematic Tool",
                           description="Determine which tool to disable from error logs",
                           action=identify_tool),
                RunbookStep(id="disable", name="Disable Tool",
                           description="Remove tool from available tool registry",
                           action=disable_tool, rollback_action=rollback_disable,
                           post_check=verify_disabled),
                RunbookStep(id="verify", name="Verify Graceful Degradation",
                           description="Confirm system handles missing tool gracefully",
                           action=lambda: "Degradation verified"),
                RunbookStep(id="notify", name="Notify Teams",
                           description="Alert dependent teams about disabled tool",
                           action=notify_teams),
            ],
            owner="platform-team",
            team="ai-platform",
            estimated_duration_minutes=5,
        )
    
    def _create_switch_provider_runbook(self) -> RunbookDefinition:
        """Runbook: Switch to fallback model provider."""
        
        def check_fallback_health():
            logger.info(f"Checking fallback model health: {self._state['fallback_model']}")
            return True  # In production: actual health check
        
        def confirm_outage():
            logger.info("Confirming primary provider outage...")
            return "Primary provider confirmed down"
        
        def switch_routing():
            old_model = self._state["active_model"]
            self._state["active_model"] = self._state["fallback_model"]
            logger.info(f"Switched from {old_model} to {self._state['active_model']}")
            return f"Routing switched to {self._state['active_model']}"
        
        def rollback_routing():
            self._state["active_model"] = "gpt-4"
            logger.info("Routing rolled back to primary model")
        
        def verify_responses():
            logger.info("Verifying responses from fallback model...")
            return "Responses verified - quality acceptable"
        
        def adjust_rate_limits():
            logger.info("Adjusting rate limits for fallback model capacity")
            return "Rate limits adjusted"
        
        return RunbookDefinition(
            id="switch_provider",
            name="Switch Model Provider",
            description="Switch to fallback model provider when primary is unavailable",
            severity=RunbookSeverity.CRITICAL,
            trigger_conditions=["model_provider_5xx > 50%", "model_provider_timeout", "provider_status_page_incident"],
            preflight_checks=[
                PreflightCheck(
                    name="fallback_healthy",
                    description="Fallback model provider is healthy and responsive",
                    check_fn=check_fallback_health,
                    severity="blocking",
                ),
                PreflightCheck(
                    name="prompts_compatible",
                    description="Current prompts are compatible with fallback model",
                    check_fn=lambda: True,
                    severity="warning",
                ),
            ],
            steps=[
                RunbookStep(id="confirm", name="Confirm Primary Outage",
                           description="Verify primary is actually down (not transient)",
                           action=confirm_outage, timeout_seconds=60),
                RunbookStep(id="switch", name="Switch Routing",
                           description="Route all traffic to fallback model",
                           action=switch_routing, rollback_action=rollback_routing),
                RunbookStep(id="verify", name="Verify Responses",
                           description="Send test queries and verify response quality",
                           action=verify_responses),
                RunbookStep(id="rate_limits", name="Adjust Rate Limits",
                           description="Adjust rate limits for fallback capacity",
                           action=adjust_rate_limits),
                RunbookStep(id="communicate", name="Update Status Page",
                           description="Update status page about degraded quality",
                           action=lambda: "Status page updated"),
            ],
            owner="platform-team",
            team="ai-platform",
            estimated_duration_minutes=3,
        )
    
    def _create_rollback_prompt_runbook(self) -> RunbookDefinition:
        """Runbook: Rollback to previous prompt version."""
        
        def check_previous_version_exists():
            return self._state["previous_prompt_version"] is not None
        
        def deploy_previous():
            old = self._state["active_prompt_version"]
            self._state["active_prompt_version"] = self._state["previous_prompt_version"]
            logger.info(f"Rolled back prompt from {old} to {self._state['active_prompt_version']}")
            return f"Deployed {self._state['active_prompt_version']}"
        
        def rollback_deploy():
            self._state["active_prompt_version"] = "v2.3"
        
        def clear_caches():
            logger.info("Clearing prompt caches...")
            return "Caches cleared"
        
        def run_golden_tests():
            logger.info("Running golden test set against rolled-back prompt...")
            return "Golden tests: 47/50 passed (94%)"
        
        return RunbookDefinition(
            id="rollback_prompt",
            name="Rollback Prompt Version",
            description="Rollback to previous known-good prompt version",
            severity=RunbookSeverity.HIGH,
            trigger_conditions=["quality_drop_after_deployment", "prompt_causing_errors", "user_complaints_spike"],
            preflight_checks=[
                PreflightCheck(
                    name="previous_version_available",
                    description="Previous prompt version exists and is deployable",
                    check_fn=check_previous_version_exists,
                    severity="blocking",
                ),
            ],
            steps=[
                RunbookStep(id="identify", name="Identify Bad Version",
                           description="Confirm which prompt version is causing issues",
                           action=lambda: f"Bad version: {self._state['active_prompt_version']}"),
                RunbookStep(id="deploy", name="Deploy Previous Version",
                           description="Switch to previous prompt version",
                           action=deploy_previous, rollback_action=rollback_deploy),
                RunbookStep(id="cache", name="Clear Prompt Caches",
                           description="Ensure no cached bad prompts are served",
                           action=clear_caches),
                RunbookStep(id="test", name="Run Golden Tests",
                           description="Verify quality recovered with previous version",
                           action=run_golden_tests),
                RunbookStep(id="block", name="Block Bad Version",
                           description="Mark bad version as non-deployable",
                           action=lambda: "Bad version blocked from redeployment"),
            ],
            owner="ml-team",
            team="ai-quality",
            estimated_duration_minutes=10,
        )
    
    def _create_rollback_retriever_runbook(self) -> RunbookDefinition:
        """Runbook: Rollback retrieval system to previous state."""
        
        def switch_index():
            old = self._state["active_index"]
            self._state["active_index"] = self._state["previous_index"]
            logger.info(f"Switched index from {old} to {self._state['active_index']}")
            return f"Active index: {self._state['active_index']}"
        
        def rollback_index():
            self._state["active_index"] = "index-v5"
        
        def run_retrieval_benchmark():
            logger.info("Running retrieval benchmark...")
            return "Recall@10: 0.82 (target: 0.80) - PASS"
        
        return RunbookDefinition(
            id="rollback_retriever",
            name="Rollback Retriever",
            description="Switch to previous known-good retrieval index",
            severity=RunbookSeverity.HIGH,
            trigger_conditions=["retrieval_recall_drop", "index_corruption_detected", "embedding_mismatch"],
            preflight_checks=[
                PreflightCheck(
                    name="previous_index_available",
                    description="Previous index snapshot exists and is queryable",
                    check_fn=lambda: True,
                    severity="blocking",
                ),
            ],
            steps=[
                RunbookStep(id="assess", name="Assess Degradation Scope",
                           description="Determine if all queries or subset affected",
                           action=lambda: "All queries affected - full rollback needed"),
                RunbookStep(id="switch", name="Switch to Previous Index",
                           description="Route queries to previous known-good index",
                           action=switch_index, rollback_action=rollback_index),
                RunbookStep(id="benchmark", name="Run Retrieval Benchmark",
                           description="Verify recall recovers on benchmark queries",
                           action=run_retrieval_benchmark),
                RunbookStep(id="monitor", name="Monitor Quality Metrics",
                           description="Watch groundedness and relevance metrics for recovery",
                           action=lambda: "Monitoring enabled - metrics recovering"),
            ],
            owner="ml-team",
            team="ai-platform",
            estimated_duration_minutes=15,
        )
    
    def _create_disable_mcp_server_runbook(self) -> RunbookDefinition:
        """Runbook: Disable a problematic MCP server."""
        
        def disconnect_mcp():
            server_id = "mcp-github"  # Would come from context
            self._state["disabled_mcp_servers"].append(server_id)
            logger.info(f"Disconnected MCP server: {server_id}")
            return f"MCP server '{server_id}' disconnected"
        
        def rollback_mcp():
            if "mcp-github" in self._state["disabled_mcp_servers"]:
                self._state["disabled_mcp_servers"].remove("mcp-github")
        
        return RunbookDefinition(
            id="disable_mcp_server",
            name="Disable MCP Server",
            description="Disconnect a malfunctioning or compromised MCP server",
            severity=RunbookSeverity.HIGH,
            trigger_conditions=["mcp_server_errors", "mcp_security_concern", "mcp_causing_loops"],
            preflight_checks=[
                PreflightCheck(
                    name="mcp_identified",
                    description="Problematic MCP server is identified",
                    check_fn=lambda: True,
                    severity="blocking",
                ),
            ],
            steps=[
                RunbookStep(id="disconnect", name="Disconnect MCP Server",
                           description="Remove MCP server from agent orchestrator",
                           action=disconnect_mcp, rollback_action=rollback_mcp),
                RunbookStep(id="update_tools", name="Update Tool Availability",
                           description="Mark tools provided by MCP server as unavailable",
                           action=lambda: "Tool availability updated"),
                RunbookStep(id="verify", name="Verify Graceful Handling",
                           description="Confirm agent handles missing tools gracefully",
                           action=lambda: "Agent gracefully handles missing MCP tools"),
            ],
            owner="platform-team",
            team="ai-platform",
            estimated_duration_minutes=5,
        )
    
    def _create_block_user_runbook(self) -> RunbookDefinition:
        """Runbook: Block an abusive tenant/user."""
        
        def verify_abuse():
            logger.info("Verifying abuse pattern...")
            return "Abuse confirmed: 500 requests/min with prompt injection attempts"
        
        def apply_block():
            user_id = "user-malicious-123"  # Would come from context
            self._state["blocked_users"].append(user_id)
            logger.info(f"Blocked user: {user_id}")
            return f"User '{user_id}' blocked at API gateway"
        
        def rollback_block():
            if "user-malicious-123" in self._state["blocked_users"]:
                self._state["blocked_users"].remove("user-malicious-123")
        
        def preserve_evidence():
            logger.info("Preserving request/response logs as evidence...")
            return "Evidence preserved: 500 requests logged to incident store"
        
        return RunbookDefinition(
            id="block_user",
            name="Block Tenant/User",
            description="Block an abusive or compromised tenant/user",
            severity=RunbookSeverity.HIGH,
            trigger_conditions=["abuse_detected", "safety_violations_from_user", "cost_spike_single_user"],
            preflight_checks=[
                PreflightCheck(
                    name="abuse_verified",
                    description="Abuse is verified (not false positive)",
                    check_fn=lambda: True,
                    severity="blocking",
                ),
            ],
            steps=[
                RunbookStep(id="verify", name="Verify Abuse",
                           description="Confirm this is genuine abuse, not false positive",
                           action=verify_abuse),
                RunbookStep(id="block", name="Apply Block",
                           description="Block user at API gateway level",
                           action=apply_block, rollback_action=rollback_block),
                RunbookStep(id="evidence", name="Preserve Evidence",
                           description="Save request/response logs for investigation",
                           action=preserve_evidence),
                RunbookStep(id="notify", name="Notify Trust & Safety",
                           description="Alert trust & safety team for review",
                           action=lambda: "Trust & Safety notified"),
            ],
            owner="trust-safety",
            team="ai-safety",
            estimated_duration_minutes=5,
        )
    
    def _create_lower_max_steps_runbook(self) -> RunbookDefinition:
        """Runbook: Lower maximum agent steps."""
        
        def lower_steps():
            old = self._state["max_agent_steps"]
            self._state["max_agent_steps"] = 5
            logger.info(f"Lowered max steps from {old} to 5")
            return f"Max steps: {old} -> 5"
        
        def rollback_steps():
            self._state["max_agent_steps"] = 20
        
        return RunbookDefinition(
            id="lower_max_steps",
            name="Lower Max Agent Steps",
            description="Reduce maximum agent steps to prevent runaway loops and cost spikes",
            severity=RunbookSeverity.MEDIUM,
            trigger_conditions=["agent_loop_detected", "cost_spike", "step_count_anomaly"],
            preflight_checks=[],
            steps=[
                RunbookStep(id="lower", name="Lower Max Steps",
                           description="Reduce max agent steps from 20 to 5",
                           action=lower_steps, rollback_action=rollback_steps),
                RunbookStep(id="monitor", name="Monitor Truncations",
                           description="Watch for legitimate tasks being truncated",
                           action=lambda: "Monitoring for truncated requests"),
                RunbookStep(id="communicate", name="Communicate Limitation",
                           description="Inform users about temporarily reduced capability",
                           action=lambda: "User communication sent"),
            ],
            owner="platform-team",
            team="ai-platform",
            estimated_duration_minutes=2,
        )
    
    def _create_force_human_approval_runbook(self) -> RunbookDefinition:
        """Runbook: Force human approval for all actions."""
        
        def enable_approval():
            self._state["human_approval_enabled"] = True
            logger.info("Human approval enabled for all write actions")
            return "Human approval gate activated"
        
        def rollback_approval():
            self._state["human_approval_enabled"] = False
        
        return RunbookDefinition(
            id="force_human_approval",
            name="Force Human Approval",
            description="Require human approval for all AI write actions",
            severity=RunbookSeverity.HIGH,
            trigger_conditions=["unintended_actions_detected", "safety_incident", "high_risk_period"],
            preflight_checks=[
                PreflightCheck(
                    name="approval_queue_ready",
                    description="Approval queue and on-call team are ready",
                    check_fn=lambda: True,
                    severity="blocking",
                ),
            ],
            steps=[
                RunbookStep(id="enable", name="Enable Human Approval",
                           description="Activate human-in-the-loop for all write actions",
                           action=enable_approval, rollback_action=rollback_approval),
                RunbookStep(id="configure_queue", name="Configure Approval Queue",
                           description="Set SLA and routing for approval requests",
                           action=lambda: "Approval queue configured: 5min SLA"),
                RunbookStep(id="notify_oncall", name="Notify Approval Team",
                           description="Alert team responsible for approvals",
                           action=lambda: "Approval team notified and staffed"),
            ],
            owner="ops-team",
            team="ai-ops",
            estimated_duration_minutes=3,
        )
    
    def _create_pause_write_actions_runbook(self) -> RunbookDefinition:
        """Runbook: Pause all write actions."""
        
        def pause_writes():
            self._state["write_actions_paused"] = True
            logger.info("All write actions paused")
            return "Write actions paused - system in read-only mode"
        
        def rollback_pause():
            self._state["write_actions_paused"] = False
        
        return RunbookDefinition(
            id="pause_write_actions",
            name="Pause Write Actions",
            description="Put AI system in read-only mode, blocking all write operations",
            severity=RunbookSeverity.CRITICAL,
            trigger_conditions=["data_corruption_suspected", "security_incident", "unintended_writes"],
            preflight_checks=[],
            steps=[
                RunbookStep(id="pause", name="Pause All Writes",
                           description="Block all write/modify/delete actions",
                           action=pause_writes, rollback_action=rollback_pause),
                RunbookStep(id="verify", name="Verify Read-Only",
                           description="Confirm no writes are getting through",
                           action=lambda: "Verified: 0 writes in last 60 seconds"),
                RunbookStep(id="audit", name="Audit Recent Writes",
                           description="Review writes from last hour for damage",
                           action=lambda: "Audited 47 writes: 3 suspicious, 44 normal"),
                RunbookStep(id="communicate", name="Inform Users",
                           description="Tell users write actions are temporarily unavailable",
                           action=lambda: "User notification: write actions temporarily unavailable"),
            ],
            owner="platform-team",
            team="ai-platform",
            estimated_duration_minutes=2,
        )
    
    def _create_purge_documents_runbook(self) -> RunbookDefinition:
        """Runbook: Purge poisoned/malicious documents from knowledge base."""
        
        def identify_documents():
            logger.info("Identifying poisoned documents by source and timestamp...")
            return "Found 23 poisoned documents from source 'compromised-feed'"
        
        def remove_from_index():
            logger.info("Removing poisoned documents from vector index...")
            return "Removed 23 documents from vector index"
        
        def remove_from_store():
            logger.info("Removing from document store...")
            return "Removed from document store"
        
        def clear_caches():
            logger.info("Clearing retrieval caches...")
            return "Caches cleared"
        
        def verify_removal():
            logger.info("Searching for known poisoned content...")
            return "Verification: 0 results for poisoned content patterns"
        
        return RunbookDefinition(
            id="purge_documents",
            name="Purge Poisoned Documents",
            description="Remove malicious or incorrect documents from knowledge base",
            severity=RunbookSeverity.HIGH,
            trigger_conditions=["poisoned_docs_detected", "malicious_ingestion", "data_quality_alert"],
            preflight_checks=[
                PreflightCheck(
                    name="documents_identified",
                    description="Specific documents to purge are identified",
                    check_fn=lambda: True,
                    severity="blocking",
                ),
                PreflightCheck(
                    name="index_writable",
                    description="Vector index is writable (not in read-only mode)",
                    check_fn=lambda: True,
                    severity="blocking",
                ),
            ],
            steps=[
                RunbookStep(id="identify", name="Identify Documents",
                           description="Find all poisoned documents by source/pattern/timestamp",
                           action=identify_documents),
                RunbookStep(id="remove_index", name="Remove from Vector Index",
                           description="Delete document embeddings from vector index",
                           action=remove_from_index),
                RunbookStep(id="remove_store", name="Remove from Document Store",
                           description="Delete source documents from storage",
                           action=remove_from_store),
                RunbookStep(id="clear_cache", name="Clear Caches",
                           description="Clear any caches serving stale results",
                           action=clear_caches),
                RunbookStep(id="verify", name="Verify Complete Removal",
                           description="Search for poisoned content, confirm zero results",
                           action=verify_removal),
                RunbookStep(id="assess_impact", name="Assess User Impact",
                           description="Check if users received responses based on poisoned docs",
                           action=lambda: "Impact: ~15 responses may have used poisoned documents"),
                RunbookStep(id="prevent", name="Add Ingestion Guards",
                           description="Add validation rules to prevent recurrence",
                           action=lambda: "Added source validation for feed 'compromised-feed'"),
            ],
            owner="ml-team",
            team="ai-platform",
            estimated_duration_minutes=20,
        )
    
    def _create_reindex_knowledge_base_runbook(self) -> RunbookDefinition:
        """Runbook: Re-index the entire knowledge base."""
        
        def validate_sources():
            logger.info("Validating source documents are intact...")
            return "Source validation: 10,245 documents, all intact"
        
        def create_new_index():
            logger.info("Creating new index alongside old...")
            return "New index 'index-v6' created"
        
        def run_embedding_pipeline():
            logger.info("Running embedding pipeline on all documents...")
            # In production: this would be an async job
            return "Embedded 10,245 documents (est. 45 minutes)"
        
        def run_benchmark():
            logger.info("Running retrieval benchmark on new index...")
            return "Recall@10: 0.84, Precision@10: 0.76 - PASS"
        
        def switch_traffic():
            self._state["active_index"] = "index-v6"
            logger.info("Switched traffic to new index")
            return "Traffic now serving from index-v6"
        
        def rollback_switch():
            self._state["active_index"] = "index-v5"
        
        return RunbookDefinition(
            id="reindex_knowledge_base",
            name="Re-index Knowledge Base",
            description="Full re-index of knowledge base with new embeddings",
            severity=RunbookSeverity.MEDIUM,
            trigger_conditions=["index_corruption", "embedding_model_upgrade", "post_purge_reindex"],
            preflight_checks=[
                PreflightCheck(
                    name="sources_intact",
                    description="Source documents are verified intact",
                    check_fn=lambda: True,
                    severity="blocking",
                ),
                PreflightCheck(
                    name="capacity_available",
                    description="Sufficient compute for embedding pipeline",
                    check_fn=lambda: True,
                    severity="blocking",
                ),
            ],
            steps=[
                RunbookStep(id="validate", name="Validate Source Documents",
                           description="Verify all source documents are intact and clean",
                           action=validate_sources),
                RunbookStep(id="create_index", name="Create New Index",
                           description="Create new index alongside existing one",
                           action=create_new_index),
                RunbookStep(id="embed", name="Run Embedding Pipeline",
                           description="Generate embeddings for all documents",
                           action=run_embedding_pipeline, timeout_seconds=7200),
                RunbookStep(id="benchmark", name="Run Retrieval Benchmark",
                           description="Validate new index with benchmark queries",
                           action=run_benchmark),
                RunbookStep(id="switch", name="Switch Traffic",
                           description="Route queries to new index",
                           action=switch_traffic, rollback_action=rollback_switch,
                           requires_confirmation=True),
                RunbookStep(id="decommission", name="Schedule Old Index Decommission",
                           description="Keep old index for 7 days, then delete",
                           action=lambda: "Old index scheduled for deletion in 7 days"),
            ],
            owner="ml-team",
            team="ai-platform",
            estimated_duration_minutes=60,
        )


# =============================================================================
# RUNBOOK AUDIT LOGGING
# =============================================================================

class RunbookAuditLog:
    """Audit log for all runbook executions."""
    
    def __init__(self):
        self._entries: list[dict] = []
    
    def log_execution(self, execution: RunbookExecution, runbook: RunbookDefinition):
        """Log a complete runbook execution."""
        entry = {
            "execution_id": execution.id,
            "runbook_id": execution.runbook_id,
            "runbook_name": runbook.name,
            "status": execution.status.value,
            "triggered_by": execution.triggered_by,
            "executor": execution.executor,
            "started_at": execution.started_at.isoformat(),
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
            "duration_seconds": (execution.completed_at - execution.started_at).total_seconds() if execution.completed_at else None,
            "preflight_results": execution.preflight_results,
            "step_results": execution.step_results,
            "notes": execution.notes,
            "trigger_context": execution.trigger_context,
        }
        self._entries.append(entry)
        logger.info(f"Audit log: runbook={runbook.name} status={execution.status.value} "
                   f"duration={entry.get('duration_seconds', 'N/A')}s")
    
    def get_history(self, runbook_id: Optional[str] = None, 
                    limit: int = 50) -> list[dict]:
        """Get execution history, optionally filtered by runbook."""
        entries = self._entries
        if runbook_id:
            entries = [e for e in entries if e["runbook_id"] == runbook_id]
        return entries[-limit:]
    
    def get_stats(self) -> dict:
        """Get aggregate statistics for runbook executions."""
        if not self._entries:
            return {"total_executions": 0}
        
        total = len(self._entries)
        by_status = defaultdict(int)
        by_runbook = defaultdict(int)
        durations = []
        
        for entry in self._entries:
            by_status[entry["status"]] += 1
            by_runbook[entry["runbook_name"]] += 1
            if entry.get("duration_seconds"):
                durations.append(entry["duration_seconds"])
        
        return {
            "total_executions": total,
            "by_status": dict(by_status),
            "by_runbook": dict(by_runbook),
            "avg_duration_seconds": statistics.mean(durations) if durations else 0,
            "success_rate": by_status.get("completed", 0) / total,
        }


# =============================================================================
# POST-RUNBOOK VERIFICATION
# =============================================================================

class PostRunbookVerifier:
    """Verifies system health after runbook execution."""
    
    def __init__(self):
        self._health_checks: list[Callable[[], tuple[bool, str]]] = []
    
    def add_health_check(self, check: Callable[[], tuple[bool, str]]):
        self._health_checks.append(check)
    
    def verify(self, wait_seconds: int = 30) -> dict:
        """
        Wait and then verify system health post-runbook.
        
        Returns verification report.
        """
        logger.info(f"Waiting {wait_seconds}s before post-runbook verification...")
        time.sleep(min(wait_seconds, 5))  # Shortened for demo
        
        results = []
        all_pass = True
        
        for check in self._health_checks:
            try:
                passed, message = check()
                results.append({"passed": passed, "message": message})
                if not passed:
                    all_pass = False
            except Exception as e:
                results.append({"passed": False, "message": f"Check error: {e}"})
                all_pass = False
        
        return {
            "verified_at": datetime.utcnow().isoformat(),
            "all_passed": all_pass,
            "checks": results,
            "recommendation": "System healthy" if all_pass else "Manual investigation needed",
        }


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    
    # Create runbook system
    engine = RunbookExecutionEngine()
    factory = AIRunbookFactory()
    audit = RunbookAuditLog()
    
    # Register all runbooks
    runbooks = factory.create_all_runbooks()
    for rb in runbooks:
        engine.register_runbook(rb)
    
    print(f"Registered {len(runbooks)} runbooks:")
    for rb in runbooks:
        print(f"  - {rb.id}: {rb.name} [{rb.severity.value}]")
    
    # Auto-approve all confirmations for demo
    engine.set_confirmation_callback(lambda title, msg: True)
    
    # Execute a runbook
    print("\n--- Executing 'switch_provider' runbook ---")
    execution = engine.execute(
        runbook_id="switch_provider",
        trigger_context={"alert": "model_provider_5xx_rate=75%", "provider": "openai"},
        triggered_by="alert",
        executor="sre-bot",
    )
    
    print(f"\nExecution result: {execution.status.value}")
    print(f"Steps completed: {len(execution.step_results)}")
    for step in execution.step_results:
        print(f"  [{step['status']}] {step['name']}: {step.get('result', step.get('error', ''))}")
    
    # Log to audit
    audit.log_execution(execution, engine._runbooks["switch_provider"])
    
    # Execute another runbook
    print("\n--- Executing 'lower_max_steps' runbook ---")
    execution2 = engine.execute(
        runbook_id="lower_max_steps",
        trigger_context={"alert": "agent_loop_detected", "request_id": "req-123"},
        triggered_by="automation",
        executor="cost-guardian",
    )
    
    print(f"Execution result: {execution2.status.value}")
    audit.log_execution(execution2, engine._runbooks["lower_max_steps"])
    
    # Print audit stats
    print(f"\nAudit Stats: {json.dumps(audit.get_stats(), indent=2)}")
    
    # Post-runbook verification
    verifier = PostRunbookVerifier()
    verifier.add_health_check(lambda: (True, "API responding normally"))
    verifier.add_health_check(lambda: (True, "Error rate < 1%"))
    verifier.add_health_check(lambda: (True, "Latency p95 < 3s"))
    
    print("\n--- Post-Runbook Verification ---")
    verification = verifier.verify(wait_seconds=5)
    print(f"All passed: {verification['all_passed']}")
    for check in verification['checks']:
        print(f"  [{'PASS' if check['passed'] else 'FAIL'}] {check['message']}")
