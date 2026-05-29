# Solution 122: Chaos Engineering Platform

## 1. Requirements Clarification

### Functional Requirements
- **Experiment Definition**: Define chaos experiments with hypothesis, fault type, blast radius
- **Fault Injection**: Inject infrastructure, application, and platform-level faults
- **Safety Controls**: Automatic abort on SLO breach, kill switches, blast radius guards
- **Observability Integration**: Correlate chaos events with metrics, traces, logs
- **Scheduling**: Automated game days, recurring experiments
- **Compliance**: Approval workflows, audit trails, risk scoring

### Non-Functional Requirements
- **Safety**: Sub-second abort response time
- **Reliability**: Chaos platform itself must be highly available (99.99%)
- **Scalability**: Support 10K+ services, hundreds of concurrent experiments
- **Auditability**: Complete audit trail of all chaos activities
- **Isolation**: Experiments must not interfere with each other

### Out of Scope
- Load testing (different tool, complementary)
- Security testing / penetration testing
- Disaster recovery orchestration (different workflow)

## 2. Capacity Estimation

### Operational Scale
- 10K microservices across 50K pods
- 100 chaos experiments per week (automated + manual)
- 20 concurrent experiments maximum
- 500 fault injection agents deployed
- Monitoring: 1M metrics/min to correlate during experiments

### Storage
- Experiment definitions: ~10K records, negligible
- Experiment runs/results: ~5K/year × 10KB = 50MB/year
- Observability correlation data: 1GB per experiment run (retained 90 days)
- Audit logs: ~100K entries/year × 1KB = 100MB/year
- Total active storage: ~500GB

### Compute
- Control plane: 5 nodes (HA)
- Fault injection agents: 1 per node (500 agents)
- Safety monitor: 3 nodes (dedicated, isolated)
- Correlation engine: 10 nodes (during active experiments)

## 3. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       CHAOS ENGINEERING PLATFORM                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌────────────────┐   ┌────────────────┐   ┌────────────────────┐          │
│  │   Experiment   │   │   Approval &   │   │    Scheduling      │          │
│  │   Designer UI  │   │   Compliance   │   │    Engine          │          │
│  └───────┬────────┘   └───────┬────────┘   └────────┬───────────┘          │
│          │                     │                      │                       │
│          ▼                     ▼                      ▼                       │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │                    CHAOS CONTROL PLANE                             │       │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │       │
│  │  │  Experiment │  │  Orchestrator │  │  Safety Monitor        │  │       │
│  │  │  Manager    │  │  (State Mach) │  │  (Independent Deploy)  │  │       │
│  │  └─────────────┘  └──────────────┘  └────────────────────────┘  │       │
│  └────────────────────────────┬─────────────────────────────────────┘       │
│                               │                                              │
│          ┌────────────────────┼─────────────────────┐                       │
│          ▼                    ▼                      ▼                       │
│  ┌──────────────┐    ┌──────────────┐      ┌──────────────┐                │
│  │ Fault Agent  │    │ Fault Agent  │      │ Fault Agent  │                │
│  │ (Node A)     │    │ (Node B)     │      │ (Node N)     │                │
│  └──────────────┘    └──────────────┘      └──────────────┘                │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │              OBSERVABILITY CORRELATION ENGINE                      │       │
│  │  ┌──────────┐  ┌──────────────┐  ┌───────────┐  ┌───────────┐  │       │
│  │  │ Metrics  │  │   Traces     │  │   Logs    │  │  Alerts   │  │       │
│  │  │ (Prom)   │  │  (Jaeger)    │  │  (Loki)   │  │ (PagerD)  │  │       │
│  │  └──────────┘  └──────────────┘  └───────────┘  └───────────┘  │       │
│  └──────────────────────────────────────────────────────────────────┘       │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 4. Detailed Design

### 4.1 Fault Injection Taxonomy & Agent

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, List
import subprocess
import signal
import os

class FaultCategory(Enum):
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    PLATFORM = "platform"

class FaultType(Enum):
    # Infrastructure
    CPU_STRESS = "cpu_stress"
    MEMORY_STRESS = "memory_stress"
    DISK_FILL = "disk_fill"
    IO_STRESS = "io_stress"
    NETWORK_LATENCY = "network_latency"
    NETWORK_LOSS = "network_loss"
    NETWORK_PARTITION = "network_partition"
    DNS_FAILURE = "dns_failure"
    
    # Application
    HTTP_LATENCY = "http_latency"
    HTTP_ERROR = "http_error"
    EXCEPTION_INJECTION = "exception_injection"
    DEPENDENCY_TIMEOUT = "dependency_timeout"
    
    # Platform
    POD_KILL = "pod_kill"
    POD_EVICTION = "pod_eviction"
    NODE_DRAIN = "node_drain"
    CONTAINER_PAUSE = "container_pause"


@dataclass
class FaultConfig:
    fault_type: FaultType
    duration_seconds: int
    intensity: float  # 0.0 to 1.0
    target_selector: Dict[str, str]  # labels, namespace, service
    parameters: Dict[str, any]


class FaultInjectionAgent:
    """
    Daemon running on each node.
    Receives fault injection commands from control plane.
    Executes faults using OS/container primitives.
    Reports status and can abort immediately.
    """
    
    def __init__(self, node_id: str, control_plane_url: str):
        self.node_id = node_id
        self.control_plane_url = control_plane_url
        self.active_faults = {}
        self.abort_flag = False
    
    def inject_fault(self, fault_id: str, config: FaultConfig) -> dict:
        """Execute fault injection based on type."""
        
        if self.abort_flag:
            return {"status": "aborted", "reason": "global abort active"}
        
        handler = self._get_handler(config.fault_type)
        process = handler.start(config)
        
        self.active_faults[fault_id] = {
            "config": config,
            "process": process,
            "started_at": datetime.utcnow()
        }
        
        return {"status": "injecting", "fault_id": fault_id}
    
    def abort_fault(self, fault_id: str):
        """Immediately stop a specific fault."""
        if fault_id in self.active_faults:
            fault = self.active_faults[fault_id]
            self._cleanup_fault(fault)
            del self.active_faults[fault_id]
    
    def abort_all(self):
        """Emergency: stop ALL active faults on this node."""
        self.abort_flag = True
        for fault_id in list(self.active_faults.keys()):
            self.abort_fault(fault_id)
        self.abort_flag = False
    
    def _get_handler(self, fault_type: FaultType):
        handlers = {
            FaultType.CPU_STRESS: CPUStressHandler(),
            FaultType.NETWORK_LATENCY: NetworkLatencyHandler(),
            FaultType.NETWORK_LOSS: NetworkLossHandler(),
            FaultType.NETWORK_PARTITION: NetworkPartitionHandler(),
            FaultType.DISK_FILL: DiskFillHandler(),
            FaultType.POD_KILL: PodKillHandler(),
            FaultType.MEMORY_STRESS: MemoryStressHandler(),
        }
        return handlers[fault_type]
    
    def _cleanup_fault(self, fault):
        """Revert fault injection - restore normal state."""
        handler = self._get_handler(fault["config"].fault_type)
        handler.revert(fault["process"], fault["config"])


class NetworkLatencyHandler:
    """Inject network latency using Linux tc (traffic control)."""
    
    def start(self, config: FaultConfig) -> dict:
        latency_ms = config.parameters.get("latency_ms", 100)
        jitter_ms = config.parameters.get("jitter_ms", 10)
        interface = config.parameters.get("interface", "eth0")
        target_ip = config.parameters.get("target_ip", None)
        
        # Use tc netem to add latency
        cmd = [
            "tc", "qdisc", "add", "dev", interface, "root", "netem",
            "delay", f"{latency_ms}ms", f"{jitter_ms}ms", "distribution", "normal"
        ]
        
        if target_ip:
            # Use iptables mark + tc filter for targeted latency
            mark = self._allocate_mark()
            self._add_iptables_mark(target_ip, mark)
            cmd = self._build_targeted_tc(interface, mark, latency_ms, jitter_ms)
        
        result = subprocess.run(cmd, capture_output=True)
        return {"interface": interface, "target_ip": target_ip, "cmd": cmd}
    
    def revert(self, process_info: dict, config: FaultConfig):
        interface = process_info.get("interface", "eth0")
        subprocess.run(["tc", "qdisc", "del", "dev", interface, "root"], 
                      capture_output=True)
        if process_info.get("target_ip"):
            self._remove_iptables_mark(process_info["target_ip"])


class PodKillHandler:
    """Kill Kubernetes pods matching selector."""
    
    def start(self, config: FaultConfig) -> dict:
        namespace = config.target_selector.get("namespace", "default")
        label_selector = config.target_selector.get("labels", "")
        kill_count = config.parameters.get("count", 1)
        
        from kubernetes import client, config as k8s_config
        k8s_config.load_incluster_config()
        v1 = client.CoreV1Api()
        
        pods = v1.list_namespaced_pod(
            namespace=namespace, 
            label_selector=label_selector
        )
        
        # Select random pods up to kill_count
        import random
        targets = random.sample(pods.items, min(kill_count, len(pods.items)))
        killed = []
        
        for pod in targets:
            v1.delete_namespaced_pod(
                name=pod.metadata.name,
                namespace=namespace,
                grace_period_seconds=0
            )
            killed.append(pod.metadata.name)
        
        return {"killed_pods": killed, "namespace": namespace}
    
    def revert(self, process_info: dict, config: FaultConfig):
        # Pods will be recreated by their controller (Deployment/StatefulSet)
        pass
```

### 4.2 Experiment Lifecycle & Orchestrator

```python
from enum import Enum
from datetime import datetime, timedelta
import asyncio

class ChaosExperimentState(Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PRE_CHECK = "pre_check"       # Running safety pre-checks
    INJECTING = "injecting"       # Fault active
    OBSERVING = "observing"       # Post-injection observation
    ROLLING_BACK = "rolling_back" # Reverting fault
    ANALYZING = "analyzing"       # Correlating results
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAILED = "failed"


@dataclass
class SteadyStateHypothesis:
    """What we expect to remain true during the experiment."""
    metric_name: str
    source: str        # prometheus, datadog, custom
    query: str         # PromQL or equivalent
    comparison: str    # 'lt', 'gt', 'eq', 'within_range'
    threshold: float
    tolerance: float   # acceptable deviation
    
    def evaluate(self, current_value: float) -> bool:
        if self.comparison == "lt":
            return current_value < self.threshold + self.tolerance
        elif self.comparison == "gt":
            return current_value > self.threshold - self.tolerance
        elif self.comparison == "within_range":
            return abs(current_value - self.threshold) <= self.tolerance
        return False


class ChaosOrchestrator:
    """
    Manages the lifecycle of chaos experiments.
    Coordinates between control plane, agents, and safety monitor.
    """
    
    def __init__(self, agent_registry, safety_monitor, observability):
        self.agent_registry = agent_registry
        self.safety_monitor = safety_monitor
        self.observability = observability
    
    async def execute_experiment(self, experiment):
        """Execute full experiment lifecycle."""
        
        try:
            # Phase 1: Pre-checks
            experiment.state = ChaosExperimentState.PRE_CHECK
            await self._run_pre_checks(experiment)
            
            # Phase 2: Record steady state
            baseline = await self._record_steady_state(experiment)
            
            # Phase 3: Inject fault
            experiment.state = ChaosExperimentState.INJECTING
            injection_result = await self._inject_with_monitoring(experiment)
            
            # Phase 4: Observe
            experiment.state = ChaosExperimentState.OBSERVING
            await asyncio.sleep(experiment.observation_duration_seconds)
            
            # Phase 5: Rollback
            experiment.state = ChaosExperimentState.ROLLING_BACK
            await self._rollback(experiment)
            
            # Phase 6: Analyze
            experiment.state = ChaosExperimentState.ANALYZING
            results = await self._analyze(experiment, baseline)
            
            experiment.state = ChaosExperimentState.COMPLETED
            experiment.results = results
            
        except AbortException as e:
            experiment.state = ChaosExperimentState.ABORTED
            experiment.abort_reason = str(e)
            await self._emergency_rollback(experiment)
        
        except Exception as e:
            experiment.state = ChaosExperimentState.FAILED
            experiment.error = str(e)
            await self._emergency_rollback(experiment)
    
    async def _run_pre_checks(self, experiment):
        """Verify system is healthy enough to run chaos."""
        checks = [
            self._check_system_health(experiment),
            self._check_no_active_incidents(),
            self._check_no_deployments_in_progress(experiment),
            self._check_blast_radius_limits(experiment),
            self._check_time_window(experiment),
        ]
        results = await asyncio.gather(*checks)
        
        for check_name, passed, reason in results:
            if not passed:
                raise PreCheckFailure(f"Pre-check failed: {check_name} - {reason}")
    
    async def _inject_with_monitoring(self, experiment):
        """Inject fault while continuously monitoring safety."""
        
        # Start safety monitoring
        monitor_task = asyncio.create_task(
            self.safety_monitor.watch(experiment)
        )
        
        # Select target agents
        agents = self.agent_registry.find_agents(experiment.target_selector)
        
        # Progressive injection (start with subset)
        for phase in experiment.injection_phases:
            target_agents = agents[:phase.target_count]
            
            # Send injection command to agents
            injection_tasks = [
                agent.inject_fault(experiment.id, experiment.fault_config)
                for agent in target_agents
            ]
            await asyncio.gather(*injection_tasks)
            
            # Wait for phase stabilization
            await asyncio.sleep(phase.stabilization_seconds)
            
            # Check if we should continue expanding
            if monitor_task.done():
                raise AbortException("Safety monitor triggered abort")
        
        return {"agents_injected": len(agents)}
    
    async def _analyze(self, experiment, baseline):
        """Correlate chaos injection with system behavior."""
        
        # Gather metrics during experiment window
        metrics = await self.observability.query_range(
            queries=experiment.hypothesis_queries,
            start=experiment.injection_start,
            end=experiment.injection_end + timedelta(minutes=5)
        )
        
        # Check steady state hypothesis
        hypothesis_results = []
        for hypothesis in experiment.hypotheses:
            values = metrics.get(hypothesis.metric_name, [])
            violations = [v for v in values if not hypothesis.evaluate(v)]
            hypothesis_results.append({
                "hypothesis": hypothesis.metric_name,
                "passed": len(violations) == 0,
                "violation_count": len(violations),
                "max_deviation": max(violations, default=0)
            })
        
        # Gather related traces and logs
        traces = await self.observability.get_traces(
            service=experiment.target_service,
            start=experiment.injection_start,
            end=experiment.injection_end
        )
        
        error_logs = await self.observability.get_logs(
            service=experiment.target_service,
            level="error",
            start=experiment.injection_start,
            end=experiment.injection_end
        )
        
        return {
            "hypothesis_results": hypothesis_results,
            "overall_passed": all(h["passed"] for h in hypothesis_results),
            "error_count": len(error_logs),
            "affected_traces": len(traces),
            "recovery_time_seconds": self._compute_recovery_time(metrics, baseline),
            "blast_radius_actual": self._compute_actual_blast_radius(metrics)
        }
```

### 4.3 Safety Monitor (Independent System)

```python
import asyncio
from datetime import datetime

class SafetyMonitor:
    """
    INDEPENDENTLY DEPLOYED safety system.
    Monitors SLOs during chaos experiments and can abort instantly.
    
    Design principles:
    - Deployed separately from chaos control plane
    - Has direct access to kill agents (bypasses orchestrator)
    - Multiple redundant monitoring paths
    - Fail-safe: if monitor itself fails, all experiments abort
    """
    
    def __init__(self, metrics_client, agent_registry, alert_manager):
        self.metrics_client = metrics_client
        self.agent_registry = agent_registry
        self.alert_manager = alert_manager
        self.abort_conditions = []
        self.heartbeat_interval = 1  # Check every second
    
    async def watch(self, experiment):
        """Continuously monitor safety conditions."""
        
        abort_conditions = self._build_abort_conditions(experiment)
        
        while experiment.state == ChaosExperimentState.INJECTING:
            # Check all abort conditions in parallel
            checks = await asyncio.gather(*[
                self._evaluate_condition(condition)
                for condition in abort_conditions
            ])
            
            for condition, violated in zip(abort_conditions, checks):
                if violated:
                    await self._trigger_abort(experiment, condition)
                    raise AbortException(
                        f"Safety abort: {condition.name} violated"
                    )
            
            await asyncio.sleep(self.heartbeat_interval)
    
    def _build_abort_conditions(self, experiment) -> list:
        """Build comprehensive abort conditions."""
        conditions = []
        
        # SLO-based conditions
        for slo in experiment.abort_on_slo_breach:
            conditions.append(AbortCondition(
                name=f"SLO: {slo.name}",
                query=slo.prometheus_query,
                threshold=slo.threshold,
                comparison="gt" if slo.higher_is_worse else "lt"
            ))
        
        # Error rate spike
        conditions.append(AbortCondition(
            name="Error rate spike",
            query=f'rate(http_requests_total{{service="{experiment.target_service}",status=~"5.."}}[1m]) / rate(http_requests_total{{service="{experiment.target_service}"}}[1m])',
            threshold=experiment.max_error_rate or 0.05,
            comparison="gt"
        ))
        
        # Cascading failure detection
        conditions.append(AbortCondition(
            name="Cascade detection",
            query=f'count(up{{job=~".*"}} == 0)',
            threshold=experiment.max_unhealthy_services or 3,
            comparison="gt"
        ))
        
        # Customer impact
        conditions.append(AbortCondition(
            name="Customer impact",
            query=f'rate(user_errors_total[1m])',
            threshold=experiment.max_customer_errors or 100,
            comparison="gt"
        ))
        
        return conditions
    
    async def _trigger_abort(self, experiment, violated_condition):
        """Emergency abort - multiple paths for reliability."""
        
        # Path 1: Direct agent abort (fastest)
        agents = self.agent_registry.find_agents(experiment.target_selector)
        abort_tasks = [agent.abort_all() for agent in agents]
        await asyncio.gather(*abort_tasks, return_exceptions=True)
        
        # Path 2: Notify orchestrator
        await self.notify_orchestrator_abort(experiment.id, violated_condition)
        
        # Path 3: Alert on-call
        await self.alert_manager.fire_alert(
            severity="critical",
            title=f"Chaos experiment {experiment.name} AUTO-ABORTED",
            description=f"Condition violated: {violated_condition.name}",
            runbook="https://wiki/chaos-abort-runbook"
        )
        
        # Path 4: Audit log
        await self.audit_log.record(
            action="experiment_aborted",
            experiment_id=experiment.id,
            reason=violated_condition.name,
            timestamp=datetime.utcnow()
        )


class BlastRadiusGuard:
    """
    Ensures chaos experiments stay within defined boundaries.
    Progressive expansion with safety gates.
    """
    
    def __init__(self):
        self.max_percentage = 0.0
        self.expansion_schedule = []
    
    def create_progressive_schedule(self, experiment) -> list:
        """
        Create phased injection plan.
        Example: 1% → 5% → 25% → 50% with validation between phases.
        """
        phases = [
            InjectionPhase(target_percentage=0.01, stabilization_seconds=60),
            InjectionPhase(target_percentage=0.05, stabilization_seconds=120),
            InjectionPhase(target_percentage=0.25, stabilization_seconds=180),
        ]
        
        # Limit by experiment's max blast radius
        max_br = experiment.max_blast_radius_percentage
        return [p for p in phases if p.target_percentage <= max_br]
    
    def validate_expansion(self, current_metrics, previous_phase) -> bool:
        """Check if safe to expand to next phase."""
        # Must pass all conditions from current phase before expanding
        return all(
            condition.evaluate(current_metrics)
            for condition in previous_phase.expansion_gates
        )
```

### 4.4 Experiment DSL

```yaml
# Example Chaos Experiment Definition (YAML DSL)
apiVersion: chaos.platform/v1
kind: ChaosExperiment
metadata:
  name: payment-service-network-latency
  team: payments
  risk_level: medium

spec:
  description: >
    Verify payment service handles 500ms network latency to database
    without customer-facing errors.
  
  hypothesis:
    steady_state:
      - metric: payment_success_rate
        source: prometheus
        query: 'rate(payment_total{status="success"}[5m]) / rate(payment_total[5m])'
        expected: ">= 0.999"
      - metric: p99_latency
        source: prometheus
        query: 'histogram_quantile(0.99, rate(payment_duration_seconds_bucket[5m]))'
        expected: "<= 2.0"
    
    expected_behavior: >
      Payment service should retry failed DB calls and serve from cache.
      Success rate should not drop below 99.9%.

  target:
    service: payment-service
    namespace: production
    selector:
      labels:
        app: payment-service
        tier: backend
    scope:
      percentage: 25  # Affect 25% of pods
      exclude:
        - payment-service-canary  # Never chaos the canary

  fault:
    type: network_latency
    parameters:
      latency_ms: 500
      jitter_ms: 50
      target_port: 5432  # PostgreSQL
      duration: 300      # 5 minutes
    
    progression:
      - phase: 1
        percentage: 5
        duration: 60
        gate: "payment_success_rate > 0.999"
      - phase: 2
        percentage: 15
        duration: 120
        gate: "payment_success_rate > 0.999"
      - phase: 3
        percentage: 25
        duration: 120

  abort_conditions:
    - metric: payment_success_rate
      threshold: 0.995
      operator: lt
    - metric: customer_errors_total_rate
      threshold: 10
      operator: gt
    - metric: revenue_per_minute
      threshold_deviation: -5%  # More than 5% revenue drop
    
  schedule:
    type: recurring
    cron: "0 14 * * 2"  # Every Tuesday 2 PM
    skip_on_incidents: true
    skip_on_deploy: true
    maintenance_window: "14:00-16:00 UTC"

  approval:
    required: true
    approvers:
      - team: payments-oncall
      - team: sre
    auto_approve_after: 72h  # If no response in 3 days
    
  notifications:
    slack:
      channel: "#chaos-experiments"
      notify_on: [start, abort, complete]
    pagerduty:
      notify_on: [abort]
```

### 4.5 Compliance & Approval Workflow

```python
class ApprovalWorkflow:
    """
    Manages approval process for chaos experiments.
    Risk-based approval requirements.
    """
    
    RISK_MATRIX = {
        "low": {"approvals_needed": 0, "auto_approve": True},
        "medium": {"approvals_needed": 1, "auto_approve": False},
        "high": {"approvals_needed": 2, "auto_approve": False},
        "critical": {"approvals_needed": 3, "auto_approve": False, "requires_sre": True}
    }
    
    def compute_risk_score(self, experiment) -> str:
        """Compute risk level based on experiment parameters."""
        score = 0
        
        # Blast radius
        if experiment.target_percentage > 50:
            score += 3
        elif experiment.target_percentage > 25:
            score += 2
        elif experiment.target_percentage > 10:
            score += 1
        
        # Service criticality
        service_tier = self.service_catalog.get_tier(experiment.target_service)
        if service_tier == "tier-0":  # Revenue-critical
            score += 3
        elif service_tier == "tier-1":
            score += 2
        
        # Fault severity
        severe_faults = {FaultType.NETWORK_PARTITION, FaultType.NODE_DRAIN, FaultType.DISK_FILL}
        if experiment.fault_type in severe_faults:
            score += 2
        
        # Environment
        if experiment.environment == "production":
            score += 2
        
        # Duration
        if experiment.duration_seconds > 600:
            score += 1
        
        if score >= 8:
            return "critical"
        elif score >= 5:
            return "high"
        elif score >= 3:
            return "medium"
        return "low"
    
    async def request_approval(self, experiment):
        """Submit experiment for approval."""
        risk_level = self.compute_risk_score(experiment)
        requirements = self.RISK_MATRIX[risk_level]
        
        if requirements["auto_approve"]:
            experiment.state = ChaosExperimentState.APPROVED
            return
        
        approval_request = {
            "experiment_id": experiment.id,
            "risk_level": risk_level,
            "approvals_needed": requirements["approvals_needed"],
            "approvers": self._get_required_approvers(experiment, requirements),
            "expires_at": datetime.utcnow() + timedelta(hours=72),
            "context": {
                "target": experiment.target_service,
                "fault": experiment.fault_type.value,
                "blast_radius": experiment.target_percentage,
                "duration": experiment.duration_seconds
            }
        }
        
        experiment.state = ChaosExperimentState.PENDING_APPROVAL
        await self.notification_service.send_approval_request(approval_request)
```

## 5. Data Model

### Database Schema (PostgreSQL)

```sql
-- Chaos experiments
CREATE TABLE chaos_experiments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    team_id UUID NOT NULL REFERENCES teams(id),
    created_by UUID NOT NULL REFERENCES users(id),
    
    -- Target
    target_service VARCHAR(255) NOT NULL,
    target_namespace VARCHAR(100),
    target_selector JSONB NOT NULL,
    target_percentage DECIMAL(5,2) DEFAULT 100.0,
    environment VARCHAR(50) NOT NULL DEFAULT 'staging',
    
    -- Fault configuration
    fault_type VARCHAR(50) NOT NULL,
    fault_parameters JSONB NOT NULL,
    duration_seconds INT NOT NULL,
    
    -- Hypothesis
    hypotheses JSONB NOT NULL,
    abort_conditions JSONB NOT NULL,
    
    -- Progression
    injection_phases JSONB,
    
    -- Lifecycle
    state VARCHAR(50) NOT NULL DEFAULT 'draft',
    risk_level VARCHAR(20),
    
    -- Schedule
    schedule_type VARCHAR(20),  -- 'one_time', 'recurring'
    cron_expression VARCHAR(100),
    next_scheduled_run TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_chaos_state ON chaos_experiments(state);
CREATE INDEX idx_chaos_team ON chaos_experiments(team_id);
CREATE INDEX idx_chaos_schedule ON chaos_experiments(next_scheduled_run) 
    WHERE state = 'scheduled';

-- Experiment runs (each execution of an experiment)
CREATE TABLE chaos_experiment_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL REFERENCES chaos_experiments(id),
    
    -- Timing
    started_at TIMESTAMP NOT NULL,
    injection_start TIMESTAMP,
    injection_end TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- State
    state VARCHAR(50) NOT NULL,
    abort_reason TEXT,
    error TEXT,
    
    -- Results
    results JSONB,
    hypothesis_passed BOOLEAN,
    recovery_time_seconds INT,
    blast_radius_actual DECIMAL(5,2),
    
    -- Metadata
    triggered_by VARCHAR(50),  -- 'manual', 'scheduled', 'gameday'
    triggered_by_user UUID REFERENCES users(id),
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_runs_experiment ON chaos_experiment_runs(experiment_id, started_at DESC);
CREATE INDEX idx_runs_state ON chaos_experiment_runs(state) WHERE state = 'injecting';

-- Approval records
CREATE TABLE chaos_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL REFERENCES chaos_experiments(id),
    
    risk_level VARCHAR(20) NOT NULL,
    approvals_needed INT NOT NULL,
    approvals_received INT DEFAULT 0,
    
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'approved', 'rejected', 'expired'
    expires_at TIMESTAMP NOT NULL,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE chaos_approval_votes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    approval_id UUID NOT NULL REFERENCES chaos_approvals(id),
    approver_id UUID NOT NULL REFERENCES users(id),
    decision VARCHAR(20) NOT NULL,  -- 'approve', 'reject'
    comment TEXT,
    voted_at TIMESTAMP DEFAULT NOW()
);

-- Audit log (immutable)
CREATE TABLE chaos_audit_log (
    id BIGSERIAL PRIMARY KEY,
    experiment_id UUID,
    run_id UUID,
    action VARCHAR(100) NOT NULL,
    actor_id UUID,
    actor_type VARCHAR(20),  -- 'user', 'system', 'safety_monitor'
    details JSONB,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_experiment ON chaos_audit_log(experiment_id, timestamp DESC);
CREATE INDEX idx_audit_timestamp ON chaos_audit_log(timestamp DESC);

-- Game day definitions
CREATE TABLE game_days (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    scheduled_date DATE,
    
    -- Sequence of experiments to run
    experiment_sequence JSONB NOT NULL,  -- ordered list of experiment_ids with delays
    
    -- Coordination
    coordinator_id UUID REFERENCES users(id),
    participants JSONB,  -- team IDs
    
    state VARCHAR(50) DEFAULT 'planned',
    created_at TIMESTAMP DEFAULT NOW()
);
```

## 6. API Design

### Experiment Management API

```
POST /v1/experiments
Authorization: Bearer <token>

Request:
{
    "name": "DB latency tolerance test",
    "description": "Verify order-service handles 200ms DB latency",
    "target": {
        "service": "order-service",
        "namespace": "production",
        "selector": {"app": "order-service"},
        "percentage": 25
    },
    "fault": {
        "type": "network_latency",
        "parameters": {
            "latency_ms": 200,
            "jitter_ms": 20,
            "target_port": 5432
        },
        "duration_seconds": 300
    },
    "hypotheses": [
        {
            "metric": "order_success_rate",
            "query": "rate(orders_total{status='success'}[1m]) / rate(orders_total[1m])",
            "expected": ">= 0.999"
        }
    ],
    "abort_conditions": [
        {"metric": "error_rate", "threshold": 0.05, "operator": "gt"}
    ],
    "progression": [
        {"percentage": 5, "duration": 60},
        {"percentage": 15, "duration": 120},
        {"percentage": 25, "duration": 120}
    ]
}

Response (201 Created):
{
    "id": "exp_abc123",
    "state": "draft",
    "risk_level": "medium",
    "approval_required": true,
    "created_at": "2024-01-15T10:00:00Z"
}
```

### Execute Experiment

```
POST /v1/experiments/{id}/run
Authorization: Bearer <token>

Response (202 Accepted):
{
    "run_id": "run_xyz789",
    "state": "pre_check",
    "message": "Experiment starting, running pre-flight checks"
}
```

### Emergency Abort

```
POST /v1/experiments/{id}/abort
Authorization: Bearer <token>

Request:
{
    "reason": "Unexpected cascade to downstream services"
}

Response (200 OK):
{
    "state": "aborted",
    "abort_confirmed": true,
    "cleanup_status": "complete",
    "time_to_abort_ms": 340
}
```

### Game Day API

```
POST /v1/gamedays
Authorization: Bearer <token>

Request:
{
    "name": "Q1 Resilience Game Day",
    "scheduled_date": "2024-02-15",
    "coordinator": "user_sre_lead",
    "experiment_sequence": [
        {"experiment_id": "exp_1", "delay_after_minutes": 10},
        {"experiment_id": "exp_2", "delay_after_minutes": 15},
        {"experiment_id": "exp_3", "delay_after_minutes": 0}
    ],
    "participants": ["team_payments", "team_orders", "team_infra"]
}
```

## 7. Scalability & Performance

### Agent Architecture
- One agent per Kubernetes node (DaemonSet deployment)
- Lightweight: <50MB memory, <1% CPU when idle
- gRPC connection to control plane (bidirectional streaming for instant commands)
- Local fault execution (no network dependency for abort)

### Control Plane Scaling
- 3-node HA deployment (leader election with Raft)
- Stateless experiment execution (state in PostgreSQL)
- Agent registry in Redis for fast lookup
- Event-driven architecture (experiments are state machines)

### Safety Monitor Independence
- **Separate deployment** from chaos control plane
- **Separate infrastructure** (different k8s cluster or bare metal)
- **Direct agent access** (can abort without going through control plane)
- **Multiple monitoring paths** (Prometheus, Datadog, direct health checks)

## 8. Reliability & Fault Tolerance

### Critical Safety Guarantees
1. **Fail-safe design**: If safety monitor loses contact with agents → agents auto-revert after timeout
2. **Heartbeat-based**: Agents revert faults if no heartbeat from control plane for 30s
3. **Idempotent revert**: Revert operations are safe to retry
4. **Independent kill paths**: 3 independent ways to stop any experiment
5. **Time-bounded faults**: Every fault has a hard maximum duration (enforced locally by agent)

### Platform HA
- Control plane: 3 replicas, Raft consensus
- Safety monitor: 3 replicas, separate infrastructure
- Agents: self-healing (DaemonSet ensures presence on every node)
- PostgreSQL: primary + sync replica + async replica

### Disaster Recovery
- Agent auto-revert timeout: 30 seconds
- Control plane recovery: <60 seconds (stateless restart)
- Full platform recovery: <5 minutes

## 9. Monitoring & Observability

### Platform Health Metrics
| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Abort response time | <1s | >3s |
| Agent heartbeat | every 5s | missing 3 consecutive |
| Safety monitor uptime | 99.99% | any downtime |
| Experiment success rate | >90% | <70% |
| Pre-check pass rate | >95% | <80% |

### Experiment Correlation Dashboard
- Timeline view: fault injection window overlaid with system metrics
- Automatic anomaly detection during chaos window
- Before/during/after comparison for all SLOs
- Affected downstream services visualization
- Recovery time measurement

### Kafka Configuration

```properties
# Chaos events topic
chaos.events.topic=chaos-experiment-events
chaos.events.partitions=12
chaos.events.replication.factor=3
chaos.events.retention.ms=7776000000  # 90 days

# Agent commands topic (low latency)
chaos.commands.topic=chaos-agent-commands
chaos.commands.partitions=50  # One per agent group
chaos.commands.replication.factor=3
chaos.commands.max.message.bytes=1048576
```

### Redis Configuration

```
# Agent registry
maxmemory 2gb
maxmemory-policy allkeys-lru

# Agent heartbeat tracking
# Key: agent:{node_id}:heartbeat
# TTL: 15 seconds (3x heartbeat interval)

# Active experiments cache
# Key: active_experiments:{service_name}
# Value: Set of experiment IDs
```

## 10. Trade-offs & Alternatives

| Decision | Chosen | Alternative | Rationale |
|----------|--------|-------------|-----------|
| Agent deployment | DaemonSet | Sidecar per pod | Less overhead, node-level access for tc/iptables |
| Safety monitor | Independent cluster | Co-located | Must survive chaos platform failures |
| Fault execution | OS primitives (tc, cgroups) | Service mesh (Istio) | More fault types, works without mesh |
| State management | PostgreSQL | etcd | Richer queries for approval workflows |
| Communication | gRPC streaming | REST polling | Sub-second command delivery |
| Progression | Automatic with gates | Manual phase advancement | Reduces human error, faster execution |

### Key Trade-offs
1. **Safety vs Coverage**: Strict abort conditions may stop experiments early, missing useful data
2. **Automation vs Control**: Fully automated game days risk unattended cascading failures
3. **Production vs Staging**: Production chaos gives real confidence but carries real risk
4. **Agent overhead vs Capability**: OS-level agents need privileged access (security concern)

## 11. Unique Considerations

### Production Safety Checklist
Before any production chaos experiment:
- [ ] Incident-free for past 24 hours
- [ ] No deployments in progress for target service
- [ ] On-call engineers aware and available
- [ ] Rollback plan verified (tested in staging)
- [ ] Customer support team notified
- [ ] Monitoring dashboards prepared
- [ ] Kill switch tested

### Chaos Maturity Model
1. **Level 1**: Manual chaos in staging only
2. **Level 2**: Automated chaos in staging, manual in production
3. **Level 3**: Automated chaos in production with safety guards
4. **Level 4**: Continuous chaos (always running at low blast radius)
5. **Level 5**: Chaos-informed architecture (systems designed for chaos resilience)

### Integration with CI/CD
```yaml
# Pipeline stage: Chaos gate
chaos_gate:
  stage: post-deploy
  script:
    - chaos run --experiment "service-latency-tolerance" --env production
    - chaos verify --hypothesis-passed
  allow_failure: false  # Block promotion if chaos fails
```

### Handling Stateful Systems
- Database chaos requires special handling (don't corrupt data)
- Queue backpressure experiments need careful monitoring
- Cache invalidation chaos must track consistency violations
- State machine corruption detection via checksums
