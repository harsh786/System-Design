# Problem 7: Infrastructure Provisioning & GitOps Automation

## The Problem

Provisioning cloud infrastructure is one of the most complex orchestration challenges:

- Provision cloud infrastructure across AWS/GCP/Azure simultaneously
- Workflows run for 30-90 minutes (VM creation, DNS propagation, cert issuance)
- Rollback entire stack on any component failure (dependency-aware teardown)
- Integrate with Terraform/Pulumi state management
- Human approval gates for production deployments
- Complete audit trail for compliance (SOC2, ISO27001, FedRAMP)
- Support blue/green and canary deployment strategies
- Drift detection and automatic remediation

## Why Temporal?

Traditional CI/CD tools (Jenkins, GitHub Actions) fail at long-running infra provisioning:
- Job timeouts kill 45-minute EKS cluster creation
- No native rollback orchestration
- Retry logic is primitive (retry entire pipeline vs. single step)
- No human-in-the-loop approval with timeout
- State is lost on runner failure
- No visibility into progress of long operations

Temporal provides: durable execution, signals for human approval, heartbeating for long polls, child workflows for dependency graphs, and queries for real-time progress.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        GitOps + Temporal Architecture                         │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌───────────────────────────────────┐
│   GitHub     │────▶│  ArgoCD /    │────▶│      Temporal Cluster             │
│   (Git Push) │     │  Flux CD     │     │                                   │
└──────────────┘     └──────────────┘     │  ┌─────────────────────────────┐  │
                                          │  │  InfraProvisioningWorkflow  │  │
┌──────────────┐     ┌──────────────┐     │  │                             │  │
│   Slack /    │◀───▶│  Approval    │◀───▶│  │  1. Plan Phase              │  │
│   PagerDuty  │     │  Service     │     │  │  2. Approval Gate           │  │
└──────────────┘     └──────────────┘     │  │  3. Apply Phase             │  │
                                          │  │  4. Verify Phase            │  │
                                          │  │  5. Promote Phase           │  │
                                          │  └─────────────────────────────┘  │
                                          └───────────────────────────────────┘
                                                         │
                          ┌──────────────────────────────┼──────────────────┐
                          │                              │                  │
                          ▼                              ▼                  ▼
                   ┌─────────────┐              ┌─────────────┐    ┌─────────────┐
                   │   AWS       │              │   GCP        │    │   Azure     │
                   │   Workers   │              │   Workers    │    │   Workers   │
                   │             │              │              │    │             │
                   │ - VPC       │              │ - VPC        │    │ - VNet      │
                   │ - EKS       │              │ - GKE        │    │ - AKS       │
                   │ - RDS       │              │ - CloudSQL   │    │ - SQL DB    │
                   │ - Route53   │              │ - CloudDNS   │    │ - DNS Zone  │
                   │ - ACM       │              │ - Cert Mgr   │    │ - Key Vault │
                   └─────────────┘              └─────────────┘    └─────────────┘
                          │                              │                  │
                          ▼                              ▼                  ▼
                   ┌─────────────┐              ┌─────────────┐    ┌─────────────┐
                   │  Terraform  │              │  Terraform   │    │  Terraform  │
                   │  State (S3) │              │  State (GCS) │    │  State(Blob)│
                   └─────────────┘              └─────────────┘    └─────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                      Dependency Graph Execution                               │
│                                                                               │
│   ┌─────┐                                                                     │
│   │ VPC │──────┬──────────────────────┐                                       │
│   └─────┘      │                      │                                       │
│                ▼                      ▼                                       │
│         ┌──────────┐          ┌──────────┐                                   │
│         │ Subnets  │          │ Security │                                   │
│         └──────────┘          │ Groups   │                                   │
│                │              └──────────┘                                   │
│                ▼                      │                                       │
│         ┌──────────┐                 │                                       │
│         │   EKS    │◀────────────────┘                                       │
│         └──────────┘                                                         │
│                │                                                              │
│         ┌──────┴──────┐                                                      │
│         ▼             ▼                                                      │
│   ┌──────────┐  ┌──────────┐                                                │
│   │   RDS    │  │   DNS    │                                                 │
│   └──────────┘  └──────────┘                                                │
│         │             │                                                      │
│         ▼             ▼                                                      │
│   ┌──────────────────────┐                                                   │
│   │     Certificate      │                                                   │
│   └──────────────────────┘                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Rollback Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Dependency-Aware Rollback                                  │
│                                                                               │
│   Forward Order:  VPC → Subnets → SG → EKS → RDS → DNS → Cert              │
│   Rollback Order: Cert → DNS → RDS → EKS → SG → Subnets → VPC             │
│                                                                               │
│   On Failure at EKS:                                                         │
│     1. Skip: Cert (not created), DNS (not created), RDS (not created)       │
│     2. Destroy: EKS (partially created - force destroy)                      │
│     3. Destroy: Security Groups                                              │
│     4. Destroy: Subnets                                                      │
│     5. Destroy: VPC                                                          │
│                                                                               │
│   Each destroy step:                                                         │
│     - Check if resource exists (may have never been created)                 │
│     - Attempt destroy with retries                                           │
│     - Handle "resource in use" (dependency not yet destroyed)                │
│     - Log to audit trail                                                     │
│     - Mark resource state in workflow                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Complete Go Implementation

```go
package infra

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

// ─────────────────────────────────────────────────────────────────────────────
// Domain Types
// ─────────────────────────────────────────────────────────────────────────────

type CloudProvider string

const (
	AWS   CloudProvider = "aws"
	GCP   CloudProvider = "gcp"
	Azure CloudProvider = "azure"
)

type Environment string

const (
	EnvDev     Environment = "dev"
	EnvStaging Environment = "staging"
	EnvProd    Environment = "prod"
)

type ResourceState string

const (
	StateNotStarted ResourceState = "not_started"
	StateCreating   ResourceState = "creating"
	StateCreated    ResourceState = "created"
	StateFailed     ResourceState = "failed"
	StateDestroying ResourceState = "destroying"
	StateDestroyed  ResourceState = "destroyed"
)

type ResourceType string

const (
	ResourceVPC             ResourceType = "vpc"
	ResourceSubnet          ResourceType = "subnet"
	ResourceSecurityGroup   ResourceType = "security_group"
	ResourceEKSCluster      ResourceType = "eks_cluster"
	ResourceRDSInstance     ResourceType = "rds_instance"
	ResourceDNSRecord       ResourceType = "dns_record"
	ResourceCertificate     ResourceType = "certificate"
	ResourceLoadBalancer    ResourceType = "load_balancer"
)

type ResourceDefinition struct {
	ID           string         `json:"id"`
	Type         ResourceType   `json:"type"`
	Name         string         `json:"name"`
	Provider     CloudProvider  `json:"provider"`
	Region       string         `json:"region"`
	Config       map[string]any `json:"config"`
	DependsOn    []string       `json:"depends_on"`
	State        ResourceState  `json:"state"`
	CloudID      string         `json:"cloud_id"`      // AWS ARN, GCP resource name, etc.
	ErrorMessage string         `json:"error_message"`
	CreatedAt    time.Time      `json:"created_at"`
	DestroyedAt  time.Time      `json:"destroyed_at"`
}

type StackDefinition struct {
	StackName    string               `json:"stack_name"`
	Environment  Environment          `json:"environment"`
	Provider     CloudProvider        `json:"provider"`
	Region       string               `json:"region"`
	Team         string               `json:"team"`
	Resources    []ResourceDefinition `json:"resources"`
	Tags         map[string]string    `json:"tags"`
	TerraformDir string               `json:"terraform_dir"`
	GitCommit    string               `json:"git_commit"`
	RequestedBy  string               `json:"requested_by"`
}

type ProvisioningRequest struct {
	RequestID   string          `json:"request_id"`
	Stack       StackDefinition `json:"stack"`
	DryRun      bool            `json:"dry_run"`
	AutoApprove bool            `json:"auto_approve"` // Only for dev
	Timeout     time.Duration   `json:"timeout"`
}

type ApprovalDecision struct {
	Approved   bool   `json:"approved"`
	ApprovedBy string `json:"approved_by"`
	Comment    string `json:"comment"`
	Timestamp  time.Time `json:"timestamp"`
}

type ProvisioningProgress struct {
	RequestID       string            `json:"request_id"`
	Phase           string            `json:"phase"`
	TotalResources  int               `json:"total_resources"`
	CreatedCount    int               `json:"created_count"`
	FailedCount     int               `json:"failed_count"`
	PendingCount    int               `json:"pending_count"`
	ResourceStates  map[string]ResourceState `json:"resource_states"`
	StartedAt       time.Time         `json:"started_at"`
	EstimatedFinish time.Time         `json:"estimated_finish"`
	CurrentStep     string            `json:"current_step"`
	AuditLog        []AuditEntry      `json:"audit_log"`
}

type AuditEntry struct {
	Timestamp time.Time `json:"timestamp"`
	Action    string    `json:"action"`
	Resource  string    `json:"resource"`
	Actor     string    `json:"actor"`
	Result    string    `json:"result"`
	Details   string    `json:"details"`
}

type TerraformPlanResult struct {
	PlanID       string `json:"plan_id"`
	AddCount     int    `json:"add_count"`
	ChangeCount  int    `json:"change_count"`
	DestroyCount int    `json:"destroy_count"`
	PlanOutput   string `json:"plan_output"`
	HasChanges   bool   `json:"has_changes"`
}

type TerraformApplyResult struct {
	Success      bool              `json:"success"`
	Outputs      map[string]string `json:"outputs"`
	ResourceIDs  map[string]string `json:"resource_ids"`
	ErrorMessage string            `json:"error_message"`
	Duration     time.Duration     `json:"duration"`
}

type ResourceHealthCheck struct {
	ResourceID string `json:"resource_id"`
	Healthy    bool   `json:"healthy"`
	Status     string `json:"status"`
	Message    string `json:"message"`
	Latency    time.Duration `json:"latency"`
}

// ─────────────────────────────────────────────────────────────────────────────
// Workflow: Infrastructure Provisioning (Main Orchestrator)
// ─────────────────────────────────────────────────────────────────────────────

func InfraProvisioningWorkflow(ctx workflow.Context, req ProvisioningRequest) (*ProvisioningProgress, error) {
	logger := workflow.GetLogger(ctx)
	logger.Info("Starting infrastructure provisioning",
		"request_id", req.RequestID,
		"stack", req.Stack.StackName,
		"environment", req.Stack.Environment,
	)

	// Initialize progress state (queryable)
	progress := &ProvisioningProgress{
		RequestID:       req.RequestID,
		Phase:           "initializing",
		TotalResources:  len(req.Stack.Resources),
		ResourceStates:  make(map[string]ResourceState),
		StartedAt:       workflow.Now(ctx),
		AuditLog:        []AuditEntry{},
	}
	for _, r := range req.Stack.Resources {
		progress.ResourceStates[r.ID] = StateNotStarted
	}

	// Register query handler for progress
	err := workflow.SetQueryHandler(ctx, "get_progress", func() (*ProvisioningProgress, error) {
		return progress, nil
	})
	if err != nil {
		return nil, fmt.Errorf("failed to register query handler: %w", err)
	}

	// Register query handler for audit log
	err = workflow.SetQueryHandler(ctx, "get_audit_log", func() ([]AuditEntry, error) {
		return progress.AuditLog, nil
	})
	if err != nil {
		return nil, fmt.Errorf("failed to register audit query handler: %w", err)
	}

	// Set search attributes for visibility
	_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
		"Environment":   string(req.Stack.Environment),
		"Team":          req.Stack.Team,
		"CloudProvider": string(req.Stack.Provider),
		"StackName":     req.Stack.StackName,
		"Phase":         "planning",
	})

	addAuditEntry(progress, "provision_started", req.Stack.StackName, req.Stack.RequestedBy, "success", "")

	// ─── Phase 1: Terraform Plan ─────────────────────────────────────────────
	progress.Phase = "planning"
	progress.CurrentStep = "Running terraform plan"

	planCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		StartToCloseTimeout: 10 * time.Minute,
		HeartbeatTimeout:    30 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval:    5 * time.Second,
			BackoffCoefficient: 2.0,
			MaximumInterval:    1 * time.Minute,
			MaximumAttempts:    3,
		},
		TaskQueue: getTaskQueueForProvider(req.Stack.Provider),
	})

	var planResult TerraformPlanResult
	err = workflow.ExecuteActivity(planCtx, RunTerraformPlan, req.Stack).Get(ctx, &planResult)
	if err != nil {
		addAuditEntry(progress, "plan_failed", req.Stack.StackName, "system", "failed", err.Error())
		return progress, fmt.Errorf("terraform plan failed: %w", err)
	}

	if !planResult.HasChanges {
		progress.Phase = "completed"
		progress.CurrentStep = "No changes detected"
		addAuditEntry(progress, "no_changes", req.Stack.StackName, "system", "success", "Infrastructure is up to date")
		return progress, nil
	}

	addAuditEntry(progress, "plan_completed", req.Stack.StackName, "system", "success",
		fmt.Sprintf("add=%d change=%d destroy=%d", planResult.AddCount, planResult.ChangeCount, planResult.DestroyCount))

	// ─── Phase 2: Human Approval Gate ────────────────────────────────────────
	if !req.AutoApprove && req.Stack.Environment == EnvProd {
		progress.Phase = "awaiting_approval"
		progress.CurrentStep = "Waiting for human approval"
		_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
			"Phase": "awaiting_approval",
		})

		// Send notification for approval
		notifyCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
			StartToCloseTimeout: 30 * time.Second,
			RetryPolicy: &temporal.RetryPolicy{
				MaximumAttempts: 3,
			},
		})
		_ = workflow.ExecuteActivity(notifyCtx, SendApprovalNotification, ApprovalNotificationRequest{
			RequestID:  req.RequestID,
			StackName:  req.Stack.StackName,
			Environment: string(req.Stack.Environment),
			PlanSummary: planResult.PlanOutput,
			RequestedBy: req.Stack.RequestedBy,
		}).Get(ctx, nil)

		// Wait for approval signal or timeout (4 hours)
		approval, err := waitForApproval(ctx, 4*time.Hour)
		if err != nil {
			addAuditEntry(progress, "approval_timeout", req.Stack.StackName, "system", "rejected", "Auto-rejected after 4 hour timeout")
			return progress, fmt.Errorf("approval timeout: %w", err)
		}

		if !approval.Approved {
			addAuditEntry(progress, "approval_rejected", req.Stack.StackName, approval.ApprovedBy, "rejected", approval.Comment)
			progress.Phase = "rejected"
			return progress, fmt.Errorf("deployment rejected by %s: %s", approval.ApprovedBy, approval.Comment)
		}

		addAuditEntry(progress, "approval_granted", req.Stack.StackName, approval.ApprovedBy, "approved", approval.Comment)
	}

	// ─── Phase 3: Execute Dependency Graph ───────────────────────────────────
	progress.Phase = "applying"
	progress.CurrentStep = "Executing resource creation"
	_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
		"Phase": "applying",
	})

	// Build dependency graph and execute in topological order
	executionOrder := buildExecutionOrder(req.Stack.Resources)

	for _, batch := range executionOrder {
		// Execute each batch in parallel (resources in same batch have no dependencies)
		var futures []workflow.Future
		for _, resource := range batch {
			progress.ResourceStates[resource.ID] = StateCreating
			progress.CurrentStep = fmt.Sprintf("Creating %s (%s)", resource.Name, resource.Type)

			future := workflow.ExecuteChildWorkflow(
				workflow.WithChildOptions(ctx, workflow.ChildWorkflowOptions{
					WorkflowID: fmt.Sprintf("create-resource-%s-%s", req.RequestID, resource.ID),
					TaskQueue:  getTaskQueueForProvider(resource.Provider),
					RetryPolicy: &temporal.RetryPolicy{
						MaximumAttempts: 2,
					},
				}),
				CreateResourceWorkflow,
				resource,
				req.Stack,
			)
			futures = append(futures, future)
		}

		// Wait for all resources in this batch
		for i, future := range futures {
			var result ResourceDefinition
			if err := future.Get(ctx, &result); err != nil {
				resource := batch[i]
				progress.ResourceStates[resource.ID] = StateFailed
				progress.FailedCount++

				addAuditEntry(progress, "resource_failed", resource.Name, "system", "failed", err.Error())

				// Trigger rollback
				logger.Error("Resource creation failed, initiating rollback",
					"resource", resource.Name,
					"error", err,
				)

				rollbackErr := executeRollback(ctx, req, progress)
				if rollbackErr != nil {
					logger.Error("Rollback also failed", "error", rollbackErr)
					addAuditEntry(progress, "rollback_failed", req.Stack.StackName, "system", "failed", rollbackErr.Error())
				}

				return progress, fmt.Errorf("resource %s failed: %w (rollback initiated)", resource.Name, err)
			}

			// Update progress
			resource := batch[i]
			progress.ResourceStates[resource.ID] = StateCreated
			progress.CreatedCount++
			req.Stack.Resources[findResourceIndex(req.Stack.Resources, resource.ID)].CloudID = result.CloudID

			addAuditEntry(progress, "resource_created", resource.Name, "system", "success", result.CloudID)
		}
	}

	// ─── Phase 4: Health Verification ────────────────────────────────────────
	progress.Phase = "verifying"
	progress.CurrentStep = "Running health checks"
	_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
		"Phase": "verifying",
	})

	healthCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		StartToCloseTimeout: 5 * time.Minute,
		HeartbeatTimeout:    30 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 5,
			InitialInterval: 30 * time.Second,
		},
	})

	var healthResults []ResourceHealthCheck
	err = workflow.ExecuteActivity(healthCtx, RunHealthChecks, req.Stack).Get(ctx, &healthResults)
	if err != nil {
		addAuditEntry(progress, "health_check_failed", req.Stack.StackName, "system", "failed", err.Error())
		// Don't rollback on health check failure - resources exist, may just need time
		progress.Phase = "degraded"
		return progress, fmt.Errorf("health checks failed: %w", err)
	}

	// ─── Phase 5: Complete ───────────────────────────────────────────────────
	progress.Phase = "completed"
	progress.CurrentStep = "All resources healthy"
	_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
		"Phase": "completed",
	})

	addAuditEntry(progress, "provision_completed", req.Stack.StackName, "system", "success",
		fmt.Sprintf("Created %d resources in %s", progress.CreatedCount, workflow.Now(ctx).Sub(progress.StartedAt)))

	return progress, nil
}

// ─────────────────────────────────────────────────────────────────────────────
// Human Approval Pattern
// ─────────────────────────────────────────────────────────────────────────────

func waitForApproval(ctx workflow.Context, timeout time.Duration) (*ApprovalDecision, error) {
	approvalCh := workflow.GetSignalChannel(ctx, "approval_decision")

	// Create a timer that fires after timeout
	timerCtx, cancelTimer := workflow.WithCancel(ctx)
	timerFuture := workflow.NewTimer(timerCtx, timeout)

	// Create selector to wait for either signal or timer
	selector := workflow.NewSelector(ctx)

	var decision ApprovalDecision
	var received bool

	selector.AddReceive(approvalCh, func(ch workflow.ReceiveChannel, more bool) {
		ch.Receive(ctx, &decision)
		received = true
		cancelTimer() // Cancel the timeout timer
	})

	selector.AddFuture(timerFuture, func(f workflow.Future) {
		// Timer fired - auto-reject
		_ = f.Get(ctx, nil)
	})

	selector.Select(ctx)

	if !received {
		return nil, fmt.Errorf("approval timed out after %s", timeout)
	}

	return &decision, nil
}

// ─────────────────────────────────────────────────────────────────────────────
// Child Workflow: Create Single Resource (with polling)
// ─────────────────────────────────────────────────────────────────────────────

func CreateResourceWorkflow(ctx workflow.Context, resource ResourceDefinition, stack StackDefinition) (*ResourceDefinition, error) {
	logger := workflow.GetLogger(ctx)

	// Activity options with long timeout for cloud resources
	ao := workflow.ActivityOptions{
		StartToCloseTimeout: 30 * time.Minute,
		HeartbeatTimeout:    60 * time.Second, // Must heartbeat every 60s
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval:        10 * time.Second,
			BackoffCoefficient:     2.0,
			MaximumInterval:        2 * time.Minute,
			MaximumAttempts:        3,
			NonRetryableErrorTypes: []string{"InvalidConfigError", "QuotaExceededError"},
		},
	}
	ctx = workflow.WithActivityOptions(ctx, ao)

	// Step 1: Initiate resource creation
	var createResult ResourceCreateResult
	err := workflow.ExecuteActivity(ctx, InitiateResourceCreation, resource, stack).Get(ctx, &createResult)
	if err != nil {
		return nil, fmt.Errorf("failed to initiate creation of %s: %w", resource.Name, err)
	}

	resource.CloudID = createResult.CloudID
	resource.State = StateCreating

	// Step 2: Poll until resource is ready (some resources take 15-30 min)
	if createResult.IsAsync {
		pollInterval := getPollingInterval(resource.Type)
		maxWait := getMaxWaitTime(resource.Type)
		startTime := workflow.Now(ctx)

		for {
			// Sleep between polls
			_ = workflow.Sleep(ctx, pollInterval)

			// Check if we've exceeded max wait time
			elapsed := workflow.Now(ctx).Sub(startTime)
			if elapsed > maxWait {
				return nil, fmt.Errorf("resource %s timed out after %s (stuck in CREATING)", resource.Name, elapsed)
			}

			// Poll resource status
			var status ResourceStatus
			err := workflow.ExecuteActivity(ctx, CheckResourceStatus, resource.CloudID, resource.Type, stack.Provider).Get(ctx, &status)
			if err != nil {
				logger.Warn("Poll failed, will retry", "resource", resource.Name, "error", err)
				continue
			}

			switch status.State {
			case "ACTIVE", "AVAILABLE", "RUNNING":
				resource.State = StateCreated
				resource.CreatedAt = workflow.Now(ctx)
				logger.Info("Resource ready", "resource", resource.Name, "cloud_id", resource.CloudID, "elapsed", elapsed)
				return &resource, nil
			case "FAILED", "ERROR":
				return nil, fmt.Errorf("resource %s entered FAILED state: %s", resource.Name, status.Message)
			case "CREATING", "PENDING", "PROVISIONING":
				logger.Info("Resource still creating",
					"resource", resource.Name,
					"elapsed", elapsed,
					"status", status.State,
				)
				continue
			}
		}
	}

	resource.State = StateCreated
	resource.CreatedAt = workflow.Now(ctx)
	return &resource, nil
}

// ─────────────────────────────────────────────────────────────────────────────
// Rollback Workflow (Dependency-Aware Teardown)
// ─────────────────────────────────────────────────────────────────────────────

func RollbackWorkflow(ctx workflow.Context, req ProvisioningRequest, progress *ProvisioningProgress) error {
	logger := workflow.GetLogger(ctx)
	logger.Info("Starting rollback", "stack", req.Stack.StackName)

	// Get resources in reverse dependency order
	reverseOrder := buildReverseExecutionOrder(req.Stack.Resources)

	ao := workflow.ActivityOptions{
		StartToCloseTimeout: 15 * time.Minute,
		HeartbeatTimeout:    30 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval:    5 * time.Second,
			BackoffCoefficient: 2.0,
			MaximumInterval:    1 * time.Minute,
			MaximumAttempts:    5, // More retries for cleanup
		},
	}
	ctx = workflow.WithActivityOptions(ctx, ao)

	var rollbackErrors []string

	for _, batch := range reverseOrder {
		var futures []workflow.Future
		for _, resource := range batch {
			// Only destroy resources that were actually created
			state := progress.ResourceStates[resource.ID]
			if state != StateCreated && state != StateCreating {
				logger.Info("Skipping resource (never created)", "resource", resource.Name, "state", state)
				continue
			}

			progress.ResourceStates[resource.ID] = StateDestroying
			future := workflow.ExecuteActivity(ctx, DestroyResource, resource, req.Stack)
			futures = append(futures, future)
		}

		for i, future := range futures {
			if err := future.Get(ctx, nil); err != nil {
				resource := batch[i]
				logger.Error("Failed to destroy resource", "resource", resource.Name, "error", err)
				rollbackErrors = append(rollbackErrors, fmt.Sprintf("%s: %s", resource.Name, err.Error()))
			} else {
				resource := batch[i]
				progress.ResourceStates[resource.ID] = StateDestroyed
			}
		}
	}

	if len(rollbackErrors) > 0 {
		return fmt.Errorf("rollback completed with %d errors: %s", len(rollbackErrors), strings.Join(rollbackErrors, "; "))
	}

	return nil
}

func executeRollback(ctx workflow.Context, req ProvisioningRequest, progress *ProvisioningProgress) error {
	childCtx := workflow.WithChildOptions(ctx, workflow.ChildWorkflowOptions{
		WorkflowID: fmt.Sprintf("rollback-%s", req.RequestID),
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 3,
		},
	})

	return workflow.ExecuteChildWorkflow(childCtx, RollbackWorkflow, req, progress).Get(ctx, nil)
}

// ─────────────────────────────────────────────────────────────────────────────
// Drift Detection Workflow (Scheduled)
// ─────────────────────────────────────────────────────────────────────────────

type DriftReport struct {
	StackName   string       `json:"stack_name"`
	CheckedAt   time.Time    `json:"checked_at"`
	DriftFound  bool         `json:"drift_found"`
	Drifts      []DriftItem  `json:"drifts"`
}

type DriftItem struct {
	ResourceID   string `json:"resource_id"`
	ResourceType string `json:"resource_type"`
	Attribute    string `json:"attribute"`
	Expected     string `json:"expected"`
	Actual       string `json:"actual"`
}

func DriftDetectionWorkflow(ctx workflow.Context, stacks []StackDefinition) (*DriftReport, error) {
	logger := workflow.GetLogger(ctx)

	ao := workflow.ActivityOptions{
		StartToCloseTimeout: 10 * time.Minute,
		HeartbeatTimeout:    30 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 3,
		},
	}
	ctx = workflow.WithActivityOptions(ctx, ao)

	var allDrifts []DriftItem

	for _, stack := range stacks {
		var report DriftReport
		err := workflow.ExecuteActivity(ctx, DetectDrift, stack).Get(ctx, &report)
		if err != nil {
			logger.Error("Drift detection failed for stack", "stack", stack.StackName, "error", err)
			continue
		}

		if report.DriftFound {
			allDrifts = append(allDrifts, report.Drifts...)

			// Notify on drift
			_ = workflow.ExecuteActivity(ctx, SendDriftAlert, stack.StackName, report.Drifts).Get(ctx, nil)
		}
	}

	return &DriftReport{
		CheckedAt:  workflow.Now(ctx),
		DriftFound: len(allDrifts) > 0,
		Drifts:     allDrifts,
	}, nil
}

// ─────────────────────────────────────────────────────────────────────────────
// Blue/Green Deployment Workflow
// ─────────────────────────────────────────────────────────────────────────────

type BlueGreenRequest struct {
	StackName    string        `json:"stack_name"`
	NewVersion   string        `json:"new_version"`
	Environment  Environment   `json:"environment"`
	Provider     CloudProvider `json:"provider"`
	CanaryWeight int           `json:"canary_weight"` // 0-100
	BakeTime     time.Duration `json:"bake_time"`
}

func BlueGreenDeploymentWorkflow(ctx workflow.Context, req BlueGreenRequest) error {
	logger := workflow.GetLogger(ctx)

	ao := workflow.ActivityOptions{
		StartToCloseTimeout: 30 * time.Minute,
		HeartbeatTimeout:    60 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 3,
		},
	}
	ctx = workflow.WithActivityOptions(ctx, ao)

	// Step 1: Deploy green environment
	logger.Info("Deploying green environment", "version", req.NewVersion)
	var greenEndpoint string
	err := workflow.ExecuteActivity(ctx, DeployGreenEnvironment, req).Get(ctx, &greenEndpoint)
	if err != nil {
		return fmt.Errorf("green deployment failed: %w", err)
	}

	// Step 2: Run smoke tests against green
	logger.Info("Running smoke tests against green", "endpoint", greenEndpoint)
	var smokeResult HealthCheckResult
	err = workflow.ExecuteActivity(ctx, RunSmokeTests, greenEndpoint).Get(ctx, &smokeResult)
	if err != nil || !smokeResult.Passed {
		// Tear down green
		_ = workflow.ExecuteActivity(ctx, DestroyGreenEnvironment, req).Get(ctx, nil)
		return fmt.Errorf("smoke tests failed: %w", err)
	}

	// Step 3: Canary - shift N% traffic to green
	if req.CanaryWeight > 0 {
		logger.Info("Starting canary", "weight", req.CanaryWeight)
		err = workflow.ExecuteActivity(ctx, ShiftTraffic, req.StackName, req.CanaryWeight).Get(ctx, nil)
		if err != nil {
			return fmt.Errorf("canary traffic shift failed: %w", err)
		}

		// Bake time - monitor metrics
		logger.Info("Baking canary", "duration", req.BakeTime)
		bakeCtx, cancelBake := workflow.WithCancel(ctx)
		bakeTimer := workflow.NewTimer(bakeCtx, req.BakeTime)

		// Also listen for rollback signal during bake
		rollbackCh := workflow.GetSignalChannel(ctx, "force_rollback")
		selector := workflow.NewSelector(ctx)

		var forceRollback bool
		selector.AddReceive(rollbackCh, func(ch workflow.ReceiveChannel, more bool) {
			ch.Receive(ctx, nil)
			forceRollback = true
			cancelBake()
		})
		selector.AddFuture(bakeTimer, func(f workflow.Future) {
			_ = f.Get(ctx, nil)
		})
		selector.Select(ctx)

		if forceRollback {
			logger.Warn("Force rollback during canary bake")
			_ = workflow.ExecuteActivity(ctx, ShiftTraffic, req.StackName, 0).Get(ctx, nil)
			_ = workflow.ExecuteActivity(ctx, DestroyGreenEnvironment, req).Get(ctx, nil)
			return fmt.Errorf("deployment rolled back by operator during bake")
		}

		// Check error rate during bake
		var metrics CanaryMetrics
		err = workflow.ExecuteActivity(ctx, GetCanaryMetrics, req.StackName).Get(ctx, &metrics)
		if err == nil && metrics.ErrorRate > 1.0 { // >1% error rate
			logger.Warn("Canary error rate too high, rolling back", "error_rate", metrics.ErrorRate)
			_ = workflow.ExecuteActivity(ctx, ShiftTraffic, req.StackName, 0).Get(ctx, nil)
			_ = workflow.ExecuteActivity(ctx, DestroyGreenEnvironment, req).Get(ctx, nil)
			return fmt.Errorf("canary error rate %.2f%% exceeds threshold", metrics.ErrorRate)
		}
	}

	// Step 4: Full cutover - 100% traffic to green
	logger.Info("Full cutover to green")
	err = workflow.ExecuteActivity(ctx, ShiftTraffic, req.StackName, 100).Get(ctx, nil)
	if err != nil {
		return fmt.Errorf("full cutover failed: %w", err)
	}

	// Step 5: Destroy blue (old) environment
	logger.Info("Destroying blue (old) environment")
	err = workflow.ExecuteActivity(ctx, DestroyBlueEnvironment, req).Get(ctx, nil)
	if err != nil {
		logger.Error("Failed to destroy blue environment (non-critical)", "error", err)
		// Not a fatal error - old env will be cleaned up by drift detection
	}

	return nil
}

// ─────────────────────────────────────────────────────────────────────────────
// Activities
// ─────────────────────────────────────────────────────────────────────────────

type InfraActivities struct {
	TerraformBinary string
	AWSConfig       AWSConfig
	SlackWebhook    string
}

type AWSConfig struct {
	Region    string
	AccountID string
	RoleARN   string
}

type ResourceCreateResult struct {
	CloudID string `json:"cloud_id"`
	IsAsync bool   `json:"is_async"` // True if we need to poll for completion
}

type ResourceStatus struct {
	State   string `json:"state"`
	Message string `json:"message"`
}

type HealthCheckResult struct {
	Passed  bool   `json:"passed"`
	Message string `json:"message"`
}

type CanaryMetrics struct {
	ErrorRate   float64 `json:"error_rate"`
	P99Latency  float64 `json:"p99_latency_ms"`
	RequestRate float64 `json:"request_rate"`
}

type ApprovalNotificationRequest struct {
	RequestID   string `json:"request_id"`
	StackName   string `json:"stack_name"`
	Environment string `json:"environment"`
	PlanSummary string `json:"plan_summary"`
	RequestedBy string `json:"requested_by"`
}

func (a *InfraActivities) RunTerraformPlan(ctx context.Context, stack StackDefinition) (*TerraformPlanResult, error) {
	activity.RecordHeartbeat(ctx, "initializing terraform")

	// In production: exec terraform plan with proper env vars
	// Here showing the pattern with heartbeating
	heartbeatTicker := time.NewTicker(10 * time.Second)
	defer heartbeatTicker.Stop()

	// Simulate terraform plan (in production: exec.Command("terraform", "plan", ...))
	activity.RecordHeartbeat(ctx, "running terraform init")

	// Check for cancellation
	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	default:
	}

	activity.RecordHeartbeat(ctx, "running terraform plan")

	// Parse plan output
	result := &TerraformPlanResult{
		PlanID:      fmt.Sprintf("plan-%d", time.Now().Unix()),
		HasChanges:  true,
		AddCount:    len(stack.Resources),
		ChangeCount: 0,
		DestroyCount: 0,
		PlanOutput:  fmt.Sprintf("Plan: %d to add, 0 to change, 0 to destroy.", len(stack.Resources)),
	}

	return result, nil
}

func (a *InfraActivities) InitiateResourceCreation(ctx context.Context, resource ResourceDefinition, stack StackDefinition) (*ResourceCreateResult, error) {
	activity.RecordHeartbeat(ctx, fmt.Sprintf("creating %s", resource.Name))

	// In production: call cloud provider APIs
	switch resource.Type {
	case ResourceVPC:
		// aws ec2 create-vpc
		return &ResourceCreateResult{
			CloudID: fmt.Sprintf("vpc-%s", resource.ID),
			IsAsync: false, // VPC creation is synchronous
		}, nil

	case ResourceEKSCluster:
		// aws eks create-cluster (takes 10-15 minutes)
		return &ResourceCreateResult{
			CloudID: fmt.Sprintf("arn:aws:eks:%s:%s:cluster/%s", stack.Region, "123456789", resource.Name),
			IsAsync: true,
		}, nil

	case ResourceRDSInstance:
		// aws rds create-db-instance (takes 5-10 minutes)
		return &ResourceCreateResult{
			CloudID: fmt.Sprintf("arn:aws:rds:%s:%s:db:%s", stack.Region, "123456789", resource.Name),
			IsAsync: true,
		}, nil

	case ResourceDNSRecord:
		return &ResourceCreateResult{
			CloudID: fmt.Sprintf("route53-%s", resource.Name),
			IsAsync: true, // DNS propagation
		}, nil

	case ResourceCertificate:
		return &ResourceCreateResult{
			CloudID: fmt.Sprintf("arn:aws:acm:%s:%s:certificate/%s", stack.Region, "123456789", resource.ID),
			IsAsync: true, // Certificate validation
		}, nil

	default:
		return &ResourceCreateResult{
			CloudID: fmt.Sprintf("%s-%s", resource.Type, resource.ID),
			IsAsync: false,
		}, nil
	}
}

func (a *InfraActivities) CheckResourceStatus(ctx context.Context, cloudID string, resourceType ResourceType, provider CloudProvider) (*ResourceStatus, error) {
	activity.RecordHeartbeat(ctx, fmt.Sprintf("checking %s", cloudID))

	// In production: call describe/get API for the resource
	// Example for EKS: aws eks describe-cluster --name ...
	// Returns: CREATING | ACTIVE | DELETING | FAILED

	return &ResourceStatus{
		State:   "ACTIVE",
		Message: "Resource is ready",
	}, nil
}

func (a *InfraActivities) DestroyResource(ctx context.Context, resource ResourceDefinition, stack StackDefinition) error {
	activity.RecordHeartbeat(ctx, fmt.Sprintf("destroying %s", resource.Name))

	if resource.CloudID == "" {
		// Resource was never created
		return nil
	}

	// In production: call delete API
	// Handle "resource not found" as success (already deleted)
	// Handle "resource in use" as retryable error

	return nil
}

func (a *InfraActivities) RunHealthChecks(ctx context.Context, stack StackDefinition) ([]ResourceHealthCheck, error) {
	var results []ResourceHealthCheck

	for _, resource := range stack.Resources {
		activity.RecordHeartbeat(ctx, fmt.Sprintf("health check: %s", resource.Name))

		results = append(results, ResourceHealthCheck{
			ResourceID: resource.ID,
			Healthy:    true,
			Status:     "healthy",
			Message:    "All checks passed",
			Latency:    100 * time.Millisecond,
		})
	}

	return results, nil
}

func (a *InfraActivities) SendApprovalNotification(ctx context.Context, req ApprovalNotificationRequest) error {
	// In production: send Slack message with approve/reject buttons
	// The buttons would call an API that signals the workflow
	activity.GetLogger(ctx).Info("Sending approval notification",
		"stack", req.StackName,
		"environment", req.Environment,
	)
	return nil
}

func (a *InfraActivities) DetectDrift(ctx context.Context, stack StackDefinition) (*DriftReport, error) {
	activity.RecordHeartbeat(ctx, fmt.Sprintf("checking drift for %s", stack.StackName))

	// In production: terraform plan -detailed-exitcode
	// Exit code 2 means drift detected
	return &DriftReport{
		StackName:  stack.StackName,
		CheckedAt:  time.Now(),
		DriftFound: false,
		Drifts:     nil,
	}, nil
}

func (a *InfraActivities) SendDriftAlert(ctx context.Context, stackName string, drifts []DriftItem) error {
	activity.GetLogger(ctx).Warn("Drift detected", "stack", stackName, "drift_count", len(drifts))
	return nil
}

func (a *InfraActivities) DeployGreenEnvironment(ctx context.Context, req BlueGreenRequest) (string, error) {
	activity.RecordHeartbeat(ctx, "deploying green environment")
	return fmt.Sprintf("https://green-%s.internal", req.StackName), nil
}

func (a *InfraActivities) RunSmokeTests(ctx context.Context, endpoint string) (*HealthCheckResult, error) {
	return &HealthCheckResult{Passed: true, Message: "All smoke tests passed"}, nil
}

func (a *InfraActivities) ShiftTraffic(ctx context.Context, stackName string, weight int) error {
	activity.RecordHeartbeat(ctx, fmt.Sprintf("shifting traffic to %d%%", weight))
	return nil
}

func (a *InfraActivities) GetCanaryMetrics(ctx context.Context, stackName string) (*CanaryMetrics, error) {
	return &CanaryMetrics{ErrorRate: 0.1, P99Latency: 45.0, RequestRate: 1000.0}, nil
}

func (a *InfraActivities) DestroyGreenEnvironment(ctx context.Context, req BlueGreenRequest) error {
	return nil
}

func (a *InfraActivities) DestroyBlueEnvironment(ctx context.Context, req BlueGreenRequest) error {
	return nil
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper Functions
// ─────────────────────────────────────────────────────────────────────────────

func getTaskQueueForProvider(provider CloudProvider) string {
	switch provider {
	case AWS:
		return "infra-aws-tq"
	case GCP:
		return "infra-gcp-tq"
	case Azure:
		return "infra-azure-tq"
	default:
		return "infra-default-tq"
	}
}

func getPollingInterval(resourceType ResourceType) time.Duration {
	switch resourceType {
	case ResourceEKSCluster:
		return 30 * time.Second // EKS takes 10-15 min
	case ResourceRDSInstance:
		return 20 * time.Second // RDS takes 5-10 min
	case ResourceCertificate:
		return 15 * time.Second
	case ResourceDNSRecord:
		return 10 * time.Second
	default:
		return 10 * time.Second
	}
}

func getMaxWaitTime(resourceType ResourceType) time.Duration {
	switch resourceType {
	case ResourceEKSCluster:
		return 25 * time.Minute
	case ResourceRDSInstance:
		return 15 * time.Minute
	case ResourceCertificate:
		return 10 * time.Minute
	case ResourceDNSRecord:
		return 5 * time.Minute
	default:
		return 10 * time.Minute
	}
}

// buildExecutionOrder returns resources grouped by execution level
// Resources in the same group can be executed in parallel
func buildExecutionOrder(resources []ResourceDefinition) [][]ResourceDefinition {
	// Kahn's algorithm for topological sort with level grouping
	inDegree := make(map[string]int)
	dependents := make(map[string][]string)
	resourceMap := make(map[string]ResourceDefinition)

	for _, r := range resources {
		resourceMap[r.ID] = r
		inDegree[r.ID] = len(r.DependsOn)
		for _, dep := range r.DependsOn {
			dependents[dep] = append(dependents[dep], r.ID)
		}
	}

	var result [][]ResourceDefinition

	// Find all nodes with no dependencies
	var queue []string
	for _, r := range resources {
		if inDegree[r.ID] == 0 {
			queue = append(queue, r.ID)
		}
	}

	for len(queue) > 0 {
		// Current batch - all can execute in parallel
		var batch []ResourceDefinition
		var nextQueue []string

		for _, id := range queue {
			batch = append(batch, resourceMap[id])
			for _, dep := range dependents[id] {
				inDegree[dep]--
				if inDegree[dep] == 0 {
					nextQueue = append(nextQueue, dep)
				}
			}
		}

		result = append(result, batch)
		queue = nextQueue
	}

	return result
}

func buildReverseExecutionOrder(resources []ResourceDefinition) [][]ResourceDefinition {
	order := buildExecutionOrder(resources)
	// Reverse the order
	for i, j := 0, len(order)-1; i < j; i, j = i+1, j-1 {
		order[i], order[j] = order[j], order[i]
	}
	return order
}

func findResourceIndex(resources []ResourceDefinition, id string) int {
	for i, r := range resources {
		if r.ID == id {
			return i
		}
	}
	return -1
}

func addAuditEntry(progress *ProvisioningProgress, action, resource, actor, result, details string) {
	progress.AuditLog = append(progress.AuditLog, AuditEntry{
		Timestamp: time.Now(),
		Action:    action,
		Resource:  resource,
		Actor:     actor,
		Result:    result,
		Details:   details,
	})
}
```

## Worker Setup

```go
package main

import (
	"log"

	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"

	infra "mycompany/infra-provisioning"
)

func main() {
	c, err := client.Dial(client.Options{
		HostPort:  "temporal.internal:7233",
		Namespace: "infrastructure",
	})
	if err != nil {
		log.Fatalf("Unable to create Temporal client: %v", err)
	}
	defer c.Close()

	// AWS worker - has AWS credentials via IAM role
	awsWorker := worker.New(c, "infra-aws-tq", worker.Options{
		MaxConcurrentActivityExecutionSize:     5,  // Limit concurrent cloud API calls
		MaxConcurrentWorkflowTaskExecutionSize: 10,
		WorkerStopTimeout:                      30 * time.Second,
	})

	activities := &infra.InfraActivities{
		TerraformBinary: "/usr/local/bin/terraform",
		AWSConfig: infra.AWSConfig{
			Region:    "us-east-1",
			AccountID: "123456789012",
			RoleARN:   "arn:aws:iam::123456789012:role/infra-provisioner",
		},
	}

	awsWorker.RegisterWorkflow(infra.InfraProvisioningWorkflow)
	awsWorker.RegisterWorkflow(infra.CreateResourceWorkflow)
	awsWorker.RegisterWorkflow(infra.RollbackWorkflow)
	awsWorker.RegisterWorkflow(infra.DriftDetectionWorkflow)
	awsWorker.RegisterWorkflow(infra.BlueGreenDeploymentWorkflow)
	awsWorker.RegisterActivity(activities)

	if err := awsWorker.Run(worker.InterruptCh()); err != nil {
		log.Fatalf("Worker failed: %v", err)
	}
}
```

## Approval Service (HTTP Handler)

```go
package main

import (
	"encoding/json"
	"net/http"
	"time"

	"go.temporal.io/sdk/client"
)

type ApprovalHandler struct {
	temporalClient client.Client
}

type ApprovalRequest struct {
	WorkflowID string `json:"workflow_id"`
	RunID      string `json:"run_id"`
	Approved   bool   `json:"approved"`
	ApprovedBy string `json:"approved_by"`
	Comment    string `json:"comment"`
}

func (h *ApprovalHandler) HandleApproval(w http.ResponseWriter, r *http.Request) {
	var req ApprovalRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid request", http.StatusBadRequest)
		return
	}

	decision := infra.ApprovalDecision{
		Approved:   req.Approved,
		ApprovedBy: req.ApprovedBy,
		Comment:    req.Comment,
		Timestamp:  time.Now(),
	}

	err := h.temporalClient.SignalWorkflow(r.Context(), req.WorkflowID, req.RunID, "approval_decision", decision)
	if err != nil {
		http.Error(w, "failed to signal workflow", http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}
```

## Failure Scenarios & Handling

### 1. Terraform Apply Timeout (Resource Stuck in CREATING)

```
Scenario: EKS cluster creation hangs for >25 minutes
Detection: Polling loop exceeds maxWaitTime
Handling:
  1. CreateResourceWorkflow returns timeout error
  2. Parent workflow catches error, triggers rollback
  3. Rollback attempts to delete the stuck resource
  4. If delete fails (resource in transitional state), retry with backoff
  5. Alert on-call if resource can't be cleaned up after 3 attempts
```

### 2. Partial Stack Creation (3 of 5 Resources Created)

```
Scenario: RDS creation fails after VPC + Subnets + EKS created
Detection: Activity returns non-retryable error (e.g., quota exceeded)
Handling:
  1. RollbackWorkflow receives list of created resources
  2. Reverse dependency order: EKS → Subnets → VPC (skip RDS - never created)
  3. Each destroy is independent and retried
  4. Terraform state is cleaned up
  5. Audit log records partial creation and rollback
```

### 3. Cloud API Rate Limiting

```
Scenario: AWS returns ThrottlingException
Detection: Activity returns retryable error
Handling:
  1. Temporal retry policy with exponential backoff (5s → 10s → 20s → 40s)
  2. Activity heartbeats continue during backoff (prevents timeout)
  3. If rate limiting persists, activity fails after MaximumAttempts
  4. Worker-level concurrency limits prevent thundering herd
  5. Separate task queues per cloud provider isolate rate limits
```

### 4. DNS Propagation Timeout

```
Scenario: DNS record created but not resolving after 5 minutes
Detection: Health check polling fails to see resolution
Handling:
  1. Polling with increasing intervals (10s, 20s, 30s)
  2. If not resolved in maxWaitTime (5 min), check if record exists
  3. If record exists but not propagating: alert, don't rollback
  4. If record doesn't exist: retry creation
  5. Continue-as-new pattern for very long waits
```

### 5. Human Approval Timeout

```
Scenario: No one approves within 4 hours
Detection: Timer fires in waitForApproval selector
Handling:
  1. Workflow auto-rejects with "timeout" reason
  2. Notification sent: "Deployment auto-rejected due to no approval"
  3. No resources were created (approval is before apply)
  4. Audit entry records the timeout
  5. Workflow completes with error (can be retried by re-triggering)
```

### 6. Certificate Validation Failure

```
Scenario: ACM certificate can't validate domain ownership
Detection: Certificate status becomes FAILED
Handling:
  1. Check if DNS validation record was created correctly
  2. Retry: delete cert, recreate with correct validation
  3. If still failing, may be DNS ownership issue - alert human
  4. Rollback proceeds with other resources if cert was blocking
```

## Production Configuration

```yaml
# temporal-worker-config.yaml
namespace: infrastructure
task_queues:
  - name: infra-aws-tq
    workers: 3
    max_concurrent_activities: 5
    max_concurrent_workflows: 20
  - name: infra-gcp-tq
    workers: 2
    max_concurrent_activities: 5
    max_concurrent_workflows: 15
  - name: infra-azure-tq
    workers: 2
    max_concurrent_activities: 5
    max_concurrent_workflows: 15

# Search attributes for visibility
search_attributes:
  Environment: Keyword
  Team: Keyword
  CloudProvider: Keyword
  StackName: Keyword
  Phase: Keyword
  RequestedBy: Keyword

# Schedule for drift detection (every 6 hours)
schedules:
  - id: drift-detection-prod
    spec:
      intervals:
        - every: 6h
    action:
      workflow: DriftDetectionWorkflow
      task_queue: infra-aws-tq
      args:
        - stacks: [prod-main, prod-data, prod-services]

# Retention
workflow_execution_retention: 90d  # SOC2 requires 90 day audit trail
```

## Metrics & Observability

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Provisioning success rate | >99% | <95% |
| Mean provisioning time | 15 min | >45 min |
| Approval response time | <1 hour | >3 hours |
| Drift detection rate | <2% | >5% |
| Rollback success rate | >99.5% | <98% |
| Worker utilization | 40-60% | >80% |
| Terraform plan time | <2 min | >5 min |

## Compliance & Audit

Every action in the workflow is recorded in the audit log, providing:

1. **Who**: Which user or system initiated/approved the action
2. **What**: Which resources were created/modified/destroyed
3. **When**: Exact timestamp of each action
4. **Why**: Linked to git commit and PR
5. **Result**: Success or failure with error details

This satisfies SOC2 CC6.1 (logical access), CC8.1 (change management), and ISO27001 A.12.1.2 (change management).
