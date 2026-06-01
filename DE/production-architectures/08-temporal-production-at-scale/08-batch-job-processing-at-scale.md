# Problem 8: Batch Job Processing at Scale (100M+ Items)

## The Problem

Processing 100M+ items in batch is a fundamental data engineering challenge:

- Nightly reconciliation jobs processing entire datasets (100M+ records)
- Dynamic partitioning based on data volume and distribution
- Respect API rate limits of downstream systems (Stripe: 100 req/s, Salesforce: 25 req/s)
- Complete within SLA window (e.g., 4-hour nightly maintenance window)
- Resumable from last checkpoint on failure (don't reprocess completed items)
- Resource-aware scheduling (don't overwhelm databases during peak hours)
- Poison pill handling (items that consistently fail shouldn't block batch)
- Progress visibility for operations team

## Why Temporal Over Traditional Batch?

| Feature | Cron + Script | Airflow | Temporal |
|---------|---------------|---------|----------|
| Mid-batch failure recovery | Restart from beginning | Restart failed task | Resume from checkpoint |
| Dynamic parallelism | Manual sharding | Fixed DAG | Child workflows, fan-out |
| Rate limiting | Application code | Not built-in | Worker-side semaphores |
| Progress tracking | Custom logging | UI shows task status | Queries + search attributes |
| Backpressure | None | None | Task queue depth monitoring |
| Duration | Limited by VM uptime | Limited by executor timeout | Unlimited (continue-as-new) |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Batch Processing Architecture                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         Coordinator Workflow                                  │
│                                                                               │
│  1. Scan data source → determine volume                                      │
│  2. Create partitions (adaptive sizing)                                      │
│  3. Fan-out: spawn child workflow per partition                               │
│  4. Monitor progress, handle failures                                        │
│  5. Aggregate results                                                        │
│  6. Report completion / SLA status                                           │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         │ Spawns N child workflows (one per partition)
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       ┌──────────┐              │
│  │Partition │  │Partition │  │Partition │  ...  │Partition │              │
│  │    1     │  │    2     │  │    3     │       │    N     │              │
│  │ 50K items│  │ 50K items│  │ 100K    │       │ 25K items│              │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘       └────┬─────┘              │
│       │              │              │                   │                    │
│       ▼              ▼              ▼                   ▼                    │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                    Task Queue: batch-processing-tq               │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Worker Pool (Auto-scaled)                             │
│                                                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Worker 1 │  │ Worker 2 │  │ Worker 3 │  │ Worker 4 │  │ Worker N │   │
│  │          │  │          │  │          │  │          │  │          │   │
│  │ Rate     │  │ Rate     │  │ Rate     │  │ Rate     │  │ Rate     │   │
│  │ Limiter  │  │ Limiter  │  │ Limiter  │  │ Limiter  │  │ Limiter  │   │
│  │ 25 req/s │  │ 25 req/s │  │ 25 req/s │  │ 25 req/s │  │ 25 req/s │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                                               │
│  Total throughput: N × 25 = configurable aggregate rate limit               │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Downstream Systems                                    │
│                                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Database   │  │  Stripe API  │  │ Salesforce   │  │    S3        │  │
│  │  (PostgreSQL)│  │  (100 req/s) │  │  (25 req/s)  │  │  (Output)    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                    Checkpoint & Resume Architecture                           │
│                                                                               │
│  Partition Workflow (processing 50K items):                                   │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Batch 1 (1000 items) ✓                                             │    │
│  │  Batch 2 (1000 items) ✓                                             │    │
│  │  Batch 3 (1000 items) ✓                                             │    │
│  │  ...                                                                 │    │
│  │  Batch 23 (1000 items) ✓  ← Last checkpoint                        │    │
│  │  Batch 24 (1000 items) ✗  ← Worker crashed here                    │    │
│  │  Batch 25-50 (not started)                                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
│  On resume (continue-as-new):                                                │
│  - Start from Batch 24 (checkpoint = 23000 items processed)                 │
│  - Skip already-processed items                                              │
│  - History stays bounded (won't hit 50K event limit)                        │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Complete Go Implementation

```go
package batch

import (
	"context"
	"fmt"
	"math"
	"sync"
	"time"

	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/worker"
	"go.temporal.io/sdk/workflow"
	"golang.org/x/time/rate"
)

// ─────────────────────────────────────────────────────────────────────────────
// Domain Types
// ─────────────────────────────────────────────────────────────────────────────

type BatchJobRequest struct {
	JobID           string        `json:"job_id"`
	JobType         string        `json:"job_type"`
	DataSource      DataSource    `json:"data_source"`
	RateLimit       RateLimitConfig `json:"rate_limit"`
	SLADeadline     time.Time     `json:"sla_deadline"`
	MaxPartitions   int           `json:"max_partitions"`
	BatchSize       int           `json:"batch_size"`        // Items per activity execution
	MaxRetries      int           `json:"max_retries"`       // Per-item retries before dead letter
	PriorityRules   []PriorityRule `json:"priority_rules"`
	ResumeFrom      *Checkpoint   `json:"resume_from"`       // nil = fresh start
}

type DataSource struct {
	Type       string            `json:"type"` // "postgres", "s3", "kafka"
	Connection string            `json:"connection"`
	Query      string            `json:"query"`
	Params     map[string]string `json:"params"`
}

type RateLimitConfig struct {
	RequestsPerSecond int           `json:"requests_per_second"`
	BurstSize         int           `json:"burst_size"`
	CooldownOnError   time.Duration `json:"cooldown_on_error"` // Back off when getting 429s
}

type PriorityRule struct {
	Condition string `json:"condition"` // e.g., "customer_tier == 'enterprise'"
	Priority  int    `json:"priority"`  // Higher = processed first
}

type Partition struct {
	ID          string    `json:"id"`
	StartKey    string    `json:"start_key"`
	EndKey      string    `json:"end_key"`
	ItemCount   int       `json:"item_count"`
	Priority    int       `json:"priority"`
	SizeClass   string    `json:"size_class"` // "small", "medium", "large"
}

type Checkpoint struct {
	PartitionID    string    `json:"partition_id"`
	LastProcessed  string    `json:"last_processed_key"`
	ItemsProcessed int       `json:"items_processed"`
	ItemsFailed    int       `json:"items_failed"`
	Timestamp      time.Time `json:"timestamp"`
}

type BatchResult struct {
	JobID           string          `json:"job_id"`
	TotalItems      int             `json:"total_items"`
	ProcessedItems  int             `json:"processed_items"`
	FailedItems     int             `json:"failed_items"`
	SkippedItems    int             `json:"skipped_items"`
	DeadLettered    int             `json:"dead_lettered"`
	Duration        time.Duration   `json:"duration"`
	Partitions      int             `json:"partitions"`
	SLAMet          bool            `json:"sla_met"`
	PartitionResults []PartitionResult `json:"partition_results"`
}

type PartitionResult struct {
	PartitionID    string        `json:"partition_id"`
	ItemsProcessed int           `json:"items_processed"`
	ItemsFailed    int           `json:"items_failed"`
	Duration       time.Duration `json:"duration"`
	Status         string        `json:"status"` // "completed", "failed", "partial"
}

type BatchProgress struct {
	JobID            string            `json:"job_id"`
	Phase            string            `json:"phase"`
	TotalItems       int               `json:"total_items"`
	ProcessedItems   int               `json:"processed_items"`
	FailedItems      int               `json:"failed_items"`
	TotalPartitions  int               `json:"total_partitions"`
	ActivePartitions int               `json:"active_partitions"`
	DonePartitions   int               `json:"done_partitions"`
	ItemsPerSecond   float64           `json:"items_per_second"`
	EstimatedFinish  time.Time         `json:"estimated_finish"`
	SLADeadline      time.Time         `json:"sla_deadline"`
	SLAAtRisk        bool              `json:"sla_at_risk"`
	PartitionStates  map[string]string `json:"partition_states"`
}

type ProcessItemsRequest struct {
	PartitionID string   `json:"partition_id"`
	Items       []Item   `json:"items"`
	JobType     string   `json:"job_type"`
}

type ProcessItemsResult struct {
	Processed    int      `json:"processed"`
	Failed       int      `json:"failed"`
	FailedItems  []string `json:"failed_items"` // IDs of failed items
	LastKey      string   `json:"last_key"`
}

type Item struct {
	ID   string         `json:"id"`
	Key  string         `json:"key"`
	Data map[string]any `json:"data"`
}

// ─────────────────────────────────────────────────────────────────────────────
// Coordinator Workflow
// ─────────────────────────────────────────────────────────────────────────────

func BatchProcessingWorkflow(ctx workflow.Context, req BatchJobRequest) (*BatchResult, error) {
	logger := workflow.GetLogger(ctx)
	logger.Info("Starting batch job", "job_id", req.JobID, "job_type", req.JobType)

	startTime := workflow.Now(ctx)

	// Initialize progress (queryable)
	progress := &BatchProgress{
		JobID:           req.JobID,
		Phase:           "initializing",
		SLADeadline:     req.SLADeadline,
		PartitionStates: make(map[string]string),
	}

	// Register query handlers
	_ = workflow.SetQueryHandler(ctx, "get_progress", func() (*BatchProgress, error) {
		return progress, nil
	})

	_ = workflow.SetQueryHandler(ctx, "get_throughput", func() (float64, error) {
		return progress.ItemsPerSecond, nil
	})

	// Set search attributes
	_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
		"JobType":    req.JobType,
		"JobID":      req.JobID,
		"Phase":      "partitioning",
		"SLAAtRisk": false,
	})

	// ─── Phase 1: Scan and Partition ─────────────────────────────────────────
	progress.Phase = "partitioning"

	partitionCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		StartToCloseTimeout: 10 * time.Minute,
		HeartbeatTimeout:    30 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 3,
		},
	})

	var partitions []Partition
	err := workflow.ExecuteActivity(partitionCtx, ScanAndPartition, req).Get(ctx, &partitions)
	if err != nil {
		return nil, fmt.Errorf("partitioning failed: %w", err)
	}

	logger.Info("Partitioning complete",
		"partitions", len(partitions),
		"total_items", sumItems(partitions),
	)

	progress.TotalPartitions = len(partitions)
	progress.TotalItems = sumItems(partitions)
	for _, p := range partitions {
		progress.PartitionStates[p.ID] = "pending"
	}

	// ─── Phase 2: Sort by Priority ───────────────────────────────────────────
	sortPartitionsByPriority(partitions)

	// ─── Phase 3: Fan-out Child Workflows ────────────────────────────────────
	progress.Phase = "processing"
	_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
		"Phase": "processing",
	})

	// Limit concurrent partitions to avoid overwhelming downstream
	maxConcurrent := min(req.MaxPartitions, len(partitions))
	if maxConcurrent == 0 {
		maxConcurrent = 10 // Default
	}

	// Use a sliding window of concurrent child workflows
	results := make([]PartitionResult, len(partitions))
	activeFutures := make(map[int]workflow.Future)
	nextPartition := 0

	// Seed initial batch
	for nextPartition < maxConcurrent && nextPartition < len(partitions) {
		future := launchPartitionWorkflow(ctx, req, partitions[nextPartition])
		activeFutures[nextPartition] = future
		progress.PartitionStates[partitions[nextPartition].ID] = "running"
		progress.ActivePartitions++
		nextPartition++
	}

	// Process completions and launch new partitions
	for len(activeFutures) > 0 {
		// Create selector to wait for any child to complete
		selector := workflow.NewSelector(ctx)

		for idx, future := range activeFutures {
			capturedIdx := idx
			capturedFuture := future
			selector.AddFuture(capturedFuture, func(f workflow.Future) {
				var result PartitionResult
				err := f.Get(ctx, &result)
				if err != nil {
					result = PartitionResult{
						PartitionID: partitions[capturedIdx].ID,
						Status:      "failed",
					}
					logger.Error("Partition failed", "partition", partitions[capturedIdx].ID, "error", err)
				}
				results[capturedIdx] = result

				// Update progress
				progress.ProcessedItems += result.ItemsProcessed
				progress.FailedItems += result.ItemsFailed
				progress.DonePartitions++
				progress.ActivePartitions--
				progress.PartitionStates[partitions[capturedIdx].ID] = result.Status

				delete(activeFutures, capturedIdx)

				// Launch next partition if available
				if nextPartition < len(partitions) {
					newFuture := launchPartitionWorkflow(ctx, req, partitions[nextPartition])
					activeFutures[nextPartition] = newFuture
					progress.PartitionStates[partitions[nextPartition].ID] = "running"
					progress.ActivePartitions++
					nextPartition++
				}
			})
		}

		selector.Select(ctx)

		// Update throughput estimate
		elapsed := workflow.Now(ctx).Sub(startTime)
		if elapsed > 0 {
			progress.ItemsPerSecond = float64(progress.ProcessedItems) / elapsed.Seconds()
		}

		// SLA check
		if progress.ItemsPerSecond > 0 {
			remainingItems := progress.TotalItems - progress.ProcessedItems
			estimatedRemaining := time.Duration(float64(remainingItems)/progress.ItemsPerSecond) * time.Second
			progress.EstimatedFinish = workflow.Now(ctx).Add(estimatedRemaining)
			progress.SLAAtRisk = progress.EstimatedFinish.After(req.SLADeadline)

			if progress.SLAAtRisk {
				_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
					"SLAAtRisk": true,
				})
				// Signal for scaling (external system monitors this)
				logger.Warn("SLA at risk",
					"estimated_finish", progress.EstimatedFinish,
					"deadline", req.SLADeadline,
					"throughput", progress.ItemsPerSecond,
				)
			}
		}
	}

	// ─── Phase 4: Aggregate Results ──────────────────────────────────────────
	progress.Phase = "aggregating"

	totalDuration := workflow.Now(ctx).Sub(startTime)

	batchResult := &BatchResult{
		JobID:            req.JobID,
		TotalItems:       progress.TotalItems,
		ProcessedItems:   progress.ProcessedItems,
		FailedItems:      progress.FailedItems,
		Duration:         totalDuration,
		Partitions:       len(partitions),
		SLAMet:           workflow.Now(ctx).Before(req.SLADeadline),
		PartitionResults: results,
	}

	// Report results
	reportCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		StartToCloseTimeout: 2 * time.Minute,
		RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 3},
	})
	_ = workflow.ExecuteActivity(reportCtx, ReportBatchCompletion, batchResult).Get(ctx, nil)

	progress.Phase = "completed"
	_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
		"Phase": "completed",
	})

	logger.Info("Batch job completed",
		"total_items", batchResult.TotalItems,
		"processed", batchResult.ProcessedItems,
		"failed", batchResult.FailedItems,
		"duration", totalDuration,
		"sla_met", batchResult.SLAMet,
	)

	return batchResult, nil
}

func launchPartitionWorkflow(ctx workflow.Context, req BatchJobRequest, partition Partition) workflow.Future {
	childCtx := workflow.WithChildOptions(ctx, workflow.ChildWorkflowOptions{
		WorkflowID: fmt.Sprintf("batch-%s-partition-%s", req.JobID, partition.ID),
		TaskQueue:  getTaskQueueForPartition(partition),
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 2, // Retry entire partition once
		},
		// ParentClosePolicy: allow partition to complete even if parent cancelled
		ParentClosePolicy: temporal.ParentClosePolicyAbandon,
	})

	return workflow.ExecuteChildWorkflow(childCtx, PartitionProcessingWorkflow, req, partition)
}

// ─────────────────────────────────────────────────────────────────────────────
// Partition Processing Workflow (with continue-as-new for checkpointing)
// ─────────────────────────────────────────────────────────────────────────────

type PartitionState struct {
	Request     BatchJobRequest `json:"request"`
	Partition   Partition       `json:"partition"`
	Checkpoint  Checkpoint      `json:"checkpoint"`
	DeadLetters []string        `json:"dead_letters"` // Item IDs that failed MaxRetries times
}

func PartitionProcessingWorkflow(ctx workflow.Context, req BatchJobRequest, partition Partition) (*PartitionResult, error) {
	return partitionProcessingInternal(ctx, &PartitionState{
		Request:   req,
		Partition: partition,
		Checkpoint: Checkpoint{
			PartitionID: partition.ID,
		},
	})
}

func PartitionProcessingResumed(ctx workflow.Context, state *PartitionState) (*PartitionResult, error) {
	return partitionProcessingInternal(ctx, state)
}

func partitionProcessingInternal(ctx workflow.Context, state *PartitionState) (*PartitionResult, error) {
	logger := workflow.GetLogger(ctx)
	startTime := workflow.Now(ctx)

	ao := workflow.ActivityOptions{
		StartToCloseTimeout: 5 * time.Minute,
		HeartbeatTimeout:    30 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval:    2 * time.Second,
			BackoffCoefficient: 2.0,
			MaximumInterval:    30 * time.Second,
			MaximumAttempts:    3,
			NonRetryableErrorTypes: []string{"PoisonPillError"},
		},
	}
	ctx = workflow.WithActivityOptions(ctx, ao)

	batchesProcessed := 0
	const maxBatchesBeforeContinueAsNew = 100 // Prevent history from growing too large

	for {
		// Fetch next batch of items
		var items []Item
		err := workflow.ExecuteActivity(ctx, FetchItemBatch, FetchRequest{
			DataSource:  state.Request.DataSource,
			PartitionID: state.Partition.ID,
			StartKey:    state.Checkpoint.LastProcessed,
			BatchSize:   state.Request.BatchSize,
		}).Get(ctx, &items)
		if err != nil {
			return nil, fmt.Errorf("failed to fetch items: %w", err)
		}

		// No more items - partition complete
		if len(items) == 0 {
			return &PartitionResult{
				PartitionID:    state.Partition.ID,
				ItemsProcessed: state.Checkpoint.ItemsProcessed,
				ItemsFailed:    state.Checkpoint.ItemsFailed,
				Duration:       workflow.Now(ctx).Sub(startTime),
				Status:         "completed",
			}, nil
		}

		// Process batch
		var result ProcessItemsResult
		err = workflow.ExecuteActivity(ctx, ProcessItemBatch, ProcessItemsRequest{
			PartitionID: state.Partition.ID,
			Items:       items,
			JobType:     state.Request.JobType,
		}).Get(ctx, &result)
		if err != nil {
			logger.Error("Batch processing failed", "partition", state.Partition.ID, "error", err)
			// On failure, we've checkpointed up to this point
			// Return partial result
			return &PartitionResult{
				PartitionID:    state.Partition.ID,
				ItemsProcessed: state.Checkpoint.ItemsProcessed,
				ItemsFailed:    state.Checkpoint.ItemsFailed,
				Duration:       workflow.Now(ctx).Sub(startTime),
				Status:         "partial",
			}, err
		}

		// Update checkpoint
		state.Checkpoint.ItemsProcessed += result.Processed
		state.Checkpoint.ItemsFailed += result.Failed
		state.Checkpoint.LastProcessed = result.LastKey
		state.Checkpoint.Timestamp = workflow.Now(ctx)

		// Dead letter failed items
		if len(result.FailedItems) > 0 {
			state.DeadLetters = append(state.DeadLetters, result.FailedItems...)
		}

		batchesProcessed++

		// Continue-as-new to keep history bounded
		if batchesProcessed >= maxBatchesBeforeContinueAsNew {
			logger.Info("Continue-as-new for history management",
				"items_processed", state.Checkpoint.ItemsProcessed,
				"batches", batchesProcessed,
			)
			return nil, workflow.NewContinueAsNewError(ctx, PartitionProcessingResumed, state)
		}
	}
}

// ─────────────────────────────────────────────────────────────────────────────
// Activities
// ─────────────────────────────────────────────────────────────────────────────

type BatchActivities struct {
	DB          *sql.DB
	RateLimiter *rate.Limiter
	mu          sync.Mutex
}

type FetchRequest struct {
	DataSource  DataSource `json:"data_source"`
	PartitionID string     `json:"partition_id"`
	StartKey    string     `json:"start_key"`
	BatchSize   int        `json:"batch_size"`
}

func (a *BatchActivities) ScanAndPartition(ctx context.Context, req BatchJobRequest) ([]Partition, error) {
	activity.RecordHeartbeat(ctx, "scanning data source")

	// Count total items and determine partition boundaries
	// In production: SELECT COUNT(*), MIN(id), MAX(id) FROM table WHERE ...
	totalItems := 100_000_000 // Example

	// Adaptive partitioning:
	// - Small partitions for "hot" data (frequently accessed, VIP customers)
	// - Large partitions for "cold" data (historical, low priority)
	targetPartitionSize := calculatePartitionSize(totalItems, req.SLADeadline)

	numPartitions := int(math.Ceil(float64(totalItems) / float64(targetPartitionSize)))
	if numPartitions > req.MaxPartitions && req.MaxPartitions > 0 {
		numPartitions = req.MaxPartitions
		targetPartitionSize = totalItems / numPartitions
	}

	activity.RecordHeartbeat(ctx, fmt.Sprintf("creating %d partitions", numPartitions))

	partitions := make([]Partition, numPartitions)
	for i := 0; i < numPartitions; i++ {
		startKey := fmt.Sprintf("%010d", i*targetPartitionSize)
		endKey := fmt.Sprintf("%010d", (i+1)*targetPartitionSize)

		sizeClass := "medium"
		if targetPartitionSize < 10000 {
			sizeClass = "small"
		} else if targetPartitionSize > 500000 {
			sizeClass = "large"
		}

		partitions[i] = Partition{
			ID:        fmt.Sprintf("p-%04d", i),
			StartKey:  startKey,
			EndKey:    endKey,
			ItemCount: targetPartitionSize,
			Priority:  0, // Default priority
			SizeClass: sizeClass,
		}
	}

	return partitions, nil
}

func (a *BatchActivities) FetchItemBatch(ctx context.Context, req FetchRequest) ([]Item, error) {
	activity.RecordHeartbeat(ctx, fmt.Sprintf("fetching batch from %s", req.StartKey))

	// In production: paginated query with cursor
	// SELECT * FROM items WHERE partition_id = $1 AND key > $2 ORDER BY key LIMIT $3
	items := make([]Item, 0, req.BatchSize)

	// ... database query ...

	return items, nil
}

func (a *BatchActivities) ProcessItemBatch(ctx context.Context, req ProcessItemsRequest) (*ProcessItemsResult, error) {
	result := &ProcessItemsResult{}
	var failedItems []string

	for i, item := range req.Items {
		// Heartbeat every 100 items
		if i%100 == 0 {
			activity.RecordHeartbeat(ctx, fmt.Sprintf("processing item %d/%d", i, len(req.Items)))
		}

		// Check for cancellation
		select {
		case <-ctx.Done():
			// Return partial result
			result.LastKey = item.Key
			return result, ctx.Err()
		default:
		}

		// Rate limiting (worker-side)
		if err := a.RateLimiter.Wait(ctx); err != nil {
			return result, fmt.Errorf("rate limiter cancelled: %w", err)
		}

		// Process single item
		if err := a.processItem(ctx, item, req.JobType); err != nil {
			failedItems = append(failedItems, item.ID)
			result.Failed++
		} else {
			result.Processed++
		}

		result.LastKey = item.Key
	}

	result.FailedItems = failedItems
	return result, nil
}

func (a *BatchActivities) processItem(ctx context.Context, item Item, jobType string) error {
	// Actual business logic per item type
	switch jobType {
	case "reconciliation":
		return a.reconcileItem(ctx, item)
	case "report_generation":
		return a.generateReport(ctx, item)
	case "data_migration":
		return a.migrateItem(ctx, item)
	default:
		return fmt.Errorf("unknown job type: %s", jobType)
	}
}

func (a *BatchActivities) reconcileItem(ctx context.Context, item Item) error {
	// Compare source of truth with derived data
	// Fix discrepancies
	return nil
}

func (a *BatchActivities) generateReport(ctx context.Context, item Item) error {
	return nil
}

func (a *BatchActivities) migrateItem(ctx context.Context, item Item) error {
	return nil
}

func (a *BatchActivities) ReportBatchCompletion(ctx context.Context, result *BatchResult) error {
	activity.RecordHeartbeat(ctx, "reporting completion")
	// Send to monitoring, Slack, etc.
	return nil
}

// Dead letter activity - moves permanently failed items to DLQ
func (a *BatchActivities) DeadLetterItems(ctx context.Context, jobID string, items []string) error {
	activity.RecordHeartbeat(ctx, fmt.Sprintf("dead-lettering %d items", len(items)))
	// INSERT INTO dead_letter_queue (job_id, item_id, failed_at) VALUES ...
	return nil
}

// ─────────────────────────────────────────────────────────────────────────────
// Backpressure Pattern
// ─────────────────────────────────────────────────────────────────────────────

// BackpressureMonitorWorkflow runs alongside batch processing
// and signals the coordinator to pause/resume based on downstream health
func BackpressureMonitorWorkflow(ctx workflow.Context, jobID string) error {
	logger := workflow.GetLogger(ctx)

	ao := workflow.ActivityOptions{
		StartToCloseTimeout: 30 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 3,
		},
	}
	ctx = workflow.WithActivityOptions(ctx, ao)

	for {
		// Check downstream system health every 30 seconds
		_ = workflow.Sleep(ctx, 30*time.Second)

		var health DownstreamHealth
		err := workflow.ExecuteActivity(ctx, CheckDownstreamHealth).Get(ctx, &health)
		if err != nil {
			logger.Warn("Health check failed", "error", err)
			continue
		}

		if health.IsOverloaded {
			logger.Warn("Downstream overloaded, signaling pause",
				"db_connections", health.DBConnections,
				"api_error_rate", health.APIErrorRate,
			)

			// Signal coordinator to pause
			err = workflow.SignalExternalWorkflow(ctx, fmt.Sprintf("batch-%s", jobID), "", "backpressure", BackpressureSignal{
				Action: "pause",
				Reason: health.OverloadReason,
			}).Get(ctx, nil)
			if err != nil {
				logger.Error("Failed to signal pause", "error", err)
			}

			// Wait for recovery
			for {
				_ = workflow.Sleep(ctx, 10*time.Second)
				var recovered DownstreamHealth
				_ = workflow.ExecuteActivity(ctx, CheckDownstreamHealth).Get(ctx, &recovered)
				if !recovered.IsOverloaded {
					break
				}
			}

			// Signal resume
			_ = workflow.SignalExternalWorkflow(ctx, fmt.Sprintf("batch-%s", jobID), "", "backpressure", BackpressureSignal{
				Action: "resume",
			}).Get(ctx, nil)
		}
	}
}

type DownstreamHealth struct {
	IsOverloaded   bool    `json:"is_overloaded"`
	OverloadReason string  `json:"overload_reason"`
	DBConnections  int     `json:"db_connections"`
	APIErrorRate   float64 `json:"api_error_rate"`
	QueueDepth     int     `json:"queue_depth"`
}

type BackpressureSignal struct {
	Action string `json:"action"` // "pause" or "resume"
	Reason string `json:"reason"`
}

func (a *BatchActivities) CheckDownstreamHealth(ctx context.Context) (*DownstreamHealth, error) {
	// Check database connection pool utilization
	// Check API error rates
	// Check queue depths
	return &DownstreamHealth{
		IsOverloaded:  false,
		DBConnections: 45,
		APIErrorRate:  0.01,
		QueueDepth:    100,
	}, nil
}

// ─────────────────────────────────────────────────────────────────────────────
// Sliding Window Rate Limiter (for rate-limited APIs)
// ─────────────────────────────────────────────────────────────────────────────

// SlidingWindowWorkflow processes items with a strict global rate limit
// Used when aggregate rate across all workers must not exceed a threshold
func SlidingWindowWorkflow(ctx workflow.Context, req BatchJobRequest) error {
	logger := workflow.GetLogger(ctx)

	// Use a local activity to acquire rate limit tokens
	// This ensures global coordination across all partition workflows

	ao := workflow.WithLocalActivityOptions(ctx, workflow.LocalActivityOptions{
		ScheduleToCloseTimeout: 5 * time.Second,
	})

	// Process items one at a time through the rate limiter
	ticker := workflow.NewTimer(ctx, time.Second/time.Duration(req.RateLimit.RequestsPerSecond))

	for {
		// Wait for rate limit token
		if err := ticker.Get(ctx, nil); err != nil {
			return err
		}

		// Process one item
		var done bool
		err := workflow.ExecuteLocalActivity(ao, func(ctx context.Context) (bool, error) {
			// Dequeue and process one item
			return false, nil
		}).Get(ctx, &done)

		if err != nil {
			logger.Error("Processing failed", "error", err)
			continue
		}

		if done {
			break
		}

		// Reset ticker
		ticker = workflow.NewTimer(ctx, time.Second/time.Duration(req.RateLimit.RequestsPerSecond))
	}

	return nil
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper Functions
// ─────────────────────────────────────────────────────────────────────────────

func sumItems(partitions []Partition) int {
	total := 0
	for _, p := range partitions {
		total += p.ItemCount
	}
	return total
}

func sortPartitionsByPriority(partitions []Partition) {
	// Sort by priority descending (higher priority first)
	// In production: sort.Slice with proper comparison
}

func getTaskQueueForPartition(partition Partition) string {
	switch partition.SizeClass {
	case "small":
		return "batch-small-tq"
	case "large":
		return "batch-large-tq"
	default:
		return "batch-medium-tq"
	}
}

func calculatePartitionSize(totalItems int, deadline time.Time) int {
	remainingTime := time.Until(deadline)
	if remainingTime <= 0 {
		return 10000 // Small partitions for urgent processing
	}

	// Target: complete in 75% of available time (25% buffer)
	availableSeconds := remainingTime.Seconds() * 0.75

	// Assume ~1000 items/second throughput per partition
	// With 10 concurrent partitions = 10K items/second
	targetThroughput := 10000.0
	partitionSize := int(targetThroughput * availableSeconds / 10.0)

	// Clamp to reasonable bounds
	if partitionSize < 1000 {
		partitionSize = 1000
	}
	if partitionSize > 1_000_000 {
		partitionSize = 1_000_000
	}

	return partitionSize
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
```

## Worker Setup with Auto-Scaling

```go
package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"sync"
	"time"

	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"
	"golang.org/x/time/rate"

	batch "mycompany/batch-processing"
)

func main() {
	c, err := client.Dial(client.Options{
		HostPort:  os.Getenv("TEMPORAL_HOST"),
		Namespace: "batch-processing",
	})
	if err != nil {
		log.Fatalf("Unable to create client: %v", err)
	}
	defer c.Close()

	// Create workers for different partition sizes
	taskQueues := []struct {
		name          string
		maxActivities int
		rateLimit     float64
	}{
		{"batch-small-tq", 20, 100.0},
		{"batch-medium-tq", 10, 50.0},
		{"batch-large-tq", 3, 25.0},
	}

	var wg sync.WaitGroup
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()

	for _, tq := range taskQueues {
		wg.Add(1)
		go func(name string, maxAct int, ratePerSec float64) {
			defer wg.Done()

			w := worker.New(c, name, worker.Options{
				MaxConcurrentActivityExecutionSize:     maxAct,
				MaxConcurrentWorkflowTaskExecutionSize: 20,
				WorkerStopTimeout:                      60 * time.Second,
			})

			activities := &batch.BatchActivities{
				RateLimiter: rate.NewLimiter(rate.Limit(ratePerSec), int(ratePerSec)),
			}

			w.RegisterWorkflow(batch.BatchProcessingWorkflow)
			w.RegisterWorkflow(batch.PartitionProcessingWorkflow)
			w.RegisterWorkflow(batch.PartitionProcessingResumed)
			w.RegisterWorkflow(batch.BackpressureMonitorWorkflow)
			w.RegisterActivity(activities)

			if err := w.Run(worker.InterruptCh()); err != nil {
				log.Printf("Worker %s failed: %v", name, err)
			}
		}(tq.name, tq.maxActivities, tq.rateLimit)
	}

	<-ctx.Done()
	wg.Wait()
}
```

## Failure Scenarios & Handling

### 1. Worker OOM on Large Partition

```
Scenario: Worker processing a 1M-item partition runs out of memory
Root cause: Loading too many items in memory at once
Detection: Worker process killed by OOM killer, activity heartbeat stops
Handling:
  1. Temporal detects heartbeat timeout (30s without heartbeat)
  2. Activity is marked as failed
  3. Retry policy kicks in - same partition on different worker
  4. The partition resumes from last checkpoint (not from beginning)
  5. Fix: reduce batch size for large partitions, stream results

Prevention:
  - Max batch size of 1000 items per activity execution
  - Worker memory limits with proper resource requests
  - Separate task queue for large partitions with fewer concurrent activities
```

### 2. Downstream API Returns 429 (Rate Limited)

```
Scenario: Stripe API returns HTTP 429 after hitting rate limit
Detection: Activity receives 429 response
Handling:
  1. Worker-side rate limiter prevents most 429s (proactive)
  2. On 429: extract Retry-After header
  3. Activity sleeps for Retry-After duration, then retries
  4. If 429 persists: activity fails with retryable error
  5. Temporal retries with backoff (2s → 4s → 8s)
  6. Backpressure monitor signals pause to all partitions

Code pattern:
  if resp.StatusCode == 429 {
      retryAfter := resp.Header.Get("Retry-After")
      dur, _ := time.ParseDuration(retryAfter + "s")
      time.Sleep(dur)
      return nil, temporal.NewApplicationError("rate limited", "RateLimited", ...)
  }
```

### 3. 5% of Items Consistently Fail (Poison Pills)

```
Scenario: Items with malformed data fail every time they're processed
Detection: Same items fail on every retry attempt
Handling:
  1. Track per-item retry count in activity
  2. After MaxRetries (e.g., 3), move item to dead letter queue
  3. Continue processing remaining items in batch
  4. Report dead-lettered count in partition result
  5. Post-batch: dead letter review workflow notifies team

Implementation:
  - Items have retry counter in ProcessItemsResult.FailedItems
  - PartitionState.DeadLetters accumulates permanently failed items
  - Coordinator aggregates dead letter count across all partitions
  - Alert if dead letter rate > 1% of total items
```

### 4. SLA Breach Detection and Escalation

```
Scenario: Processing throughput drops, estimated finish exceeds SLA deadline
Detection: Coordinator calculates estimated finish time each cycle
Handling:
  1. SLAAtRisk search attribute set to true (visible in Temporal UI)
  2. Alert fires via monitoring (Datadog, PagerDuty)
  3. Options for operators:
     a. Scale up workers (more pods via HPA)
     b. Increase partition concurrency (signal coordinator)
     c. Skip non-critical partitions (signal coordinator)
     d. Extend SLA window (if possible)
  4. Auto-scaling: Kubernetes HPA watches pending task queue depth

Metrics:
  - temporal_workflow_task_schedule_to_start_latency > 5s → scale up
  - batch_items_per_second < threshold → alert
```

### 5. Worker Scaling During Batch

```
Scenario: Need to scale from 5 to 20 workers mid-batch
Detection: Pending activities in task queue increasing
Handling:
  1. New workers register on same task queue
  2. Temporal automatically distributes pending activities
  3. No workflow code changes needed
  4. Rate limiter is per-worker, so aggregate rate = N × per_worker_rate
  5. If aggregate rate must be fixed: use Temporal-side rate limiting

  Worker rate limiting options:
  a. Per-worker: rate.NewLimiter(globalRate / expectedWorkers)
  b. Distributed rate limiter: Redis-based token bucket
  c. Temporal resource-based tuning (experimental)
```

## Production Configuration

```yaml
# kubernetes/batch-worker-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: batch-worker-medium
spec:
  replicas: 10
  template:
    spec:
      containers:
        - name: worker
          image: mycompany/batch-worker:latest
          resources:
            requests:
              memory: "2Gi"
              cpu: "1000m"
            limits:
              memory: "4Gi"
              cpu: "2000m"
          env:
            - name: TEMPORAL_HOST
              value: "temporal.internal:7233"
            - name: TASK_QUEUE
              value: "batch-medium-tq"
            - name: RATE_LIMIT_PER_SECOND
              value: "50"
---
# HPA for auto-scaling based on Temporal queue depth
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: batch-worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: batch-worker-medium
  minReplicas: 5
  maxReplicas: 50
  metrics:
    - type: External
      external:
        metric:
          name: temporal_activity_schedule_to_start_latency_p99
        target:
          type: Value
          value: "5000"  # Scale up if p99 > 5s
```

```yaml
# temporal-config.yaml
search_attributes:
  JobType: Keyword
  JobID: Keyword
  Phase: Keyword
  SLAAtRisk: Bool

# Schedule nightly batch
schedules:
  - id: nightly-reconciliation
    spec:
      calendars:
        - hour: 2  # 2 AM
          minute: 0
    action:
      workflow: BatchProcessingWorkflow
      task_queue: batch-medium-tq
      args:
        - job_type: "reconciliation"
          sla_deadline: "+4h"
          max_partitions: 100
          batch_size: 1000
```

## Metrics & Observability

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `batch_total_items` | Total items to process | - |
| `batch_items_processed` | Items successfully processed | - |
| `batch_items_per_second` | Current throughput | < 5000 items/s |
| `batch_partition_duration_p99` | Slowest partition | > 30 min |
| `batch_dead_letter_rate` | % items dead-lettered | > 1% |
| `batch_sla_remaining_seconds` | Time until SLA breach | < 30 min |
| `temporal_schedule_to_start_p99` | Activity queue wait time | > 5s |
| `worker_activity_slots_available` | Free activity slots | < 2 |

## Key Design Decisions

1. **Child workflow per partition** (not activity per partition): Allows each partition to have its own retry/checkpoint logic, and can continue-as-new independently.

2. **Continue-as-new at 100 batches**: Prevents workflow history from exceeding Temporal's 50K event limit. With 1000 items/batch, that's 100K items per history.

3. **Separate task queues by size class**: Large partitions need more memory and time. Isolating them prevents head-of-line blocking.

4. **Worker-side rate limiting**: More responsive than Temporal-side. Each worker has `rate.Limiter` to smooth out API calls.

5. **Backpressure as separate workflow**: Decouples monitoring from processing. Can be independently deployed and doesn't add to coordinator history.
