# Problem 10: Multi-Region Data Replication & Consistency

## The Problem

Global applications must replicate data across geographic regions while managing:

- Replicate critical data across 5 geographic regions (US-East, US-West, EU, APAC, LATAM)
- Configurable consistency guarantees (eventual, causal, strong)
- Handle network partitions and split-brain scenarios gracefully
- Conflict resolution for concurrent writes from multiple regions
- Compliance: data residency requirements (GDPR, data sovereignty laws)
- 99.999% availability across regions (< 5.26 minutes downtime/year)
- Sub-100ms replication for active-active workloads
- Automatic failover when a region goes offline

## Why Temporal for Replication?

| Challenge | Custom Solution | Temporal |
|-----------|----------------|----------|
| Retry failed replications | Custom retry logic + dead letters | Built-in retry policies |
| Track replication state | Custom state machine + DB | Workflow state (durable) |
| Conflict resolution | Custom merge logic + locks | Workflow with human-in-the-loop |
| Failover coordination | ZooKeeper / etcd consensus | Temporal multi-cluster |
| Audit trail | Custom logging | Workflow history |
| Region health monitoring | Custom health checks | Heartbeating activities |
| Scheduled consistency checks | Cron jobs | Scheduled workflows |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│               Multi-Region Data Replication Architecture                      │
└─────────────────────────────────────────────────────────────────────────────┘

                         ┌─────────────────────┐
                         │   Global DNS        │
                         │   (Route53/CloudFlare)│
                         │   Latency-based     │
                         └──────────┬──────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          │                         │                         │
          ▼                         ▼                         ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   US-EAST       │    │   EU-WEST       │    │   APAC          │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │  Temporal   │ │    │ │  Temporal   │ │    │ │  Temporal   │ │
│ │  Cluster    │◀├────├─┤  Cluster    │◀├────├─┤  Cluster    │ │
│ │  (Primary)  │─├────├─▶  (Standby)  │─├────├─▶  (Standby)  │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │  Workers    │ │    │ │  Workers    │ │    │ │  Workers    │ │
│ │ (Region TQ) │ │    │ │ (Region TQ) │ │    │ │ (Region TQ) │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │  Database   │ │    │ │  Database   │ │    │ │  Database   │ │
│ │  (Primary)  │─├────├─▶ (Replica)   │ │    │ │ (Replica)   │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
          │                         │                         │
          └─────────────────────────┼─────────────────────────┘
                                    │
                         ┌──────────▼──────────┐
                         │  Replication        │
                         │  Coordinator        │
                         │  Workflow           │
                         └─────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                    Consistency Models                                         │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  EVENTUAL CONSISTENCY                                                │    │
│  │  - Write to local region → async replicate to others                │    │
│  │  - Replication lag: 50-500ms (cross-region network)                 │    │
│  │  - Conflicts possible (last-writer-wins or merge)                   │    │
│  │  - Use case: user preferences, analytics, non-critical data        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  CAUSAL CONSISTENCY                                                  │    │
│  │  - Write to local → replicate with vector clock                     │    │
│  │  - Causally related writes ordered correctly                         │    │
│  │  - Concurrent writes may still conflict                             │    │
│  │  - Use case: messages, comments, collaborative editing              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  STRONG CONSISTENCY                                                  │    │
│  │  - Write to primary region → sync replicate to quorum               │    │
│  │  - All reads see latest write (linearizable)                        │    │
│  │  - Higher latency (cross-region round trip)                         │    │
│  │  - Use case: financial transactions, inventory counts               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                    Conflict Resolution Flow                                   │
│                                                                               │
│  Region A writes X=1 at T1  ───┐                                            │
│                                  ├──▶ Conflict Detected                      │
│  Region B writes X=2 at T1  ───┘         │                                  │
│                                           ▼                                  │
│                              ┌─────────────────────────┐                     │
│                              │  Resolution Strategy    │                     │
│                              ├─────────────────────────┤                     │
│                              │ 1. Last-Writer-Wins     │                     │
│                              │    (timestamp-based)    │                     │
│                              │ 2. Merge (CRDTs)       │                     │
│                              │ 3. Application logic    │                     │
│                              │ 4. Human intervention   │                     │
│                              └─────────────────────────┘                     │
│                                           │                                  │
│                                           ▼                                  │
│                              ┌─────────────────────────┐                     │
│                              │  Resolved value         │                     │
│                              │  replicated to ALL      │                     │
│                              │  regions                │                     │
│                              └─────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Complete Go Implementation

```go
package replication

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

// ─────────────────────────────────────────────────────────────────────────────
// Domain Types
// ─────────────────────────────────────────────────────────────────────────────

type Region string

const (
	RegionUSEast Region = "us-east-1"
	RegionUSWest Region = "us-west-2"
	RegionEU     Region = "eu-west-1"
	RegionAPAC   Region = "ap-southeast-1"
	RegionLATAM  Region = "sa-east-1"
)

var AllRegions = []Region{RegionUSEast, RegionUSWest, RegionEU, RegionAPAC, RegionLATAM}

type ConsistencyLevel string

const (
	ConsistencyEventual ConsistencyLevel = "eventual"
	ConsistencyCausal   ConsistencyLevel = "causal"
	ConsistencyStrong   ConsistencyLevel = "strong"
)

type ConflictStrategy string

const (
	ConflictLastWriterWins ConflictStrategy = "last_writer_wins"
	ConflictMerge          ConflictStrategy = "merge"
	ConflictAppLogic       ConflictStrategy = "application_logic"
	ConflictHumanResolve   ConflictStrategy = "human_resolution"
)

type DataEntity struct {
	EntityID    string         `json:"entity_id"`
	EntityType  string         `json:"entity_type"`
	Version     int64          `json:"version"`
	Data        []byte         `json:"data"`
	Checksum    string         `json:"checksum"`
	SourceRegion Region        `json:"source_region"`
	UpdatedAt   time.Time      `json:"updated_at"`
	VectorClock map[Region]int64 `json:"vector_clock"`
	Metadata    map[string]string `json:"metadata"`
}

type ReplicationRequest struct {
	Entity           DataEntity       `json:"entity"`
	TargetRegions    []Region         `json:"target_regions"`
	Consistency      ConsistencyLevel `json:"consistency"`
	ConflictStrategy ConflictStrategy `json:"conflict_strategy"`
	DataResidency    []DataResidencyRule `json:"data_residency"`
	SLAMaxLatency    time.Duration    `json:"sla_max_latency"`
}

type DataResidencyRule struct {
	DataClassification string   `json:"data_classification"` // "pii", "financial", "general"
	AllowedRegions     []Region `json:"allowed_regions"`
	ProhibitedRegions  []Region `json:"prohibited_regions"`
}

type ReplicationResult struct {
	EntityID       string                     `json:"entity_id"`
	SourceRegion   Region                     `json:"source_region"`
	RegionResults  map[Region]RegionSyncResult `json:"region_results"`
	Consistency    ConsistencyLevel           `json:"consistency"`
	TotalLatency   time.Duration              `json:"total_latency"`
	ConflictsFound int                        `json:"conflicts_found"`
	Success        bool                       `json:"success"`
}

type RegionSyncResult struct {
	Region     Region        `json:"region"`
	Success    bool          `json:"success"`
	Latency    time.Duration `json:"latency"`
	Error      string        `json:"error,omitempty"`
	Version    int64         `json:"version"`
	ConflictResolved bool   `json:"conflict_resolved"`
}

type RegionHealth struct {
	Region        Region        `json:"region"`
	Healthy       bool          `json:"healthy"`
	Latency       time.Duration `json:"latency"`
	LastChecked   time.Time     `json:"last_checked"`
	ErrorRate     float64       `json:"error_rate"`
	ReplicationLag time.Duration `json:"replication_lag"`
	Status        string        `json:"status"` // "active", "degraded", "offline"
}

type Conflict struct {
	EntityID    string       `json:"entity_id"`
	RegionA     Region       `json:"region_a"`
	RegionB     Region       `json:"region_b"`
	VersionA    DataEntity   `json:"version_a"`
	VersionB    DataEntity   `json:"version_b"`
	DetectedAt  time.Time    `json:"detected_at"`
	ResolvedAt  time.Time    `json:"resolved_at"`
	Resolution  string       `json:"resolution"`
	ResolvedBy  string       `json:"resolved_by"`
}

type FailoverRequest struct {
	FailedRegion  Region `json:"failed_region"`
	TargetRegion  Region `json:"target_region"`
	Reason        string `json:"reason"`
	Automatic     bool   `json:"automatic"`
}

type ReplicationProgress struct {
	EntityID       string                 `json:"entity_id"`
	Phase          string                 `json:"phase"`
	RegionStatuses map[Region]string      `json:"region_statuses"`
	Conflicts      []Conflict             `json:"conflicts"`
	StartedAt      time.Time              `json:"started_at"`
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Replication Workflow
// ─────────────────────────────────────────────────────────────────────────────

func DataReplicationWorkflow(ctx workflow.Context, req ReplicationRequest) (*ReplicationResult, error) {
	logger := workflow.GetLogger(ctx)
	logger.Info("Starting data replication",
		"entity_id", req.Entity.EntityID,
		"source_region", req.Entity.SourceRegion,
		"consistency", req.Consistency,
		"targets", len(req.TargetRegions),
	)

	startTime := workflow.Now(ctx)

	// Initialize progress
	progress := &ReplicationProgress{
		EntityID:       req.Entity.EntityID,
		Phase:          "validating",
		RegionStatuses: make(map[Region]string),
		StartedAt:      startTime,
	}
	for _, r := range req.TargetRegions {
		progress.RegionStatuses[r] = "pending"
	}

	_ = workflow.SetQueryHandler(ctx, "get_progress", func() (*ReplicationProgress, error) {
		return progress, nil
	})

	_ = workflow.UpsertSearchAttributes(ctx, map[string]interface{}{
		"EntityID":     req.Entity.EntityID,
		"EntityType":   req.Entity.EntityType,
		"SourceRegion": string(req.Entity.SourceRegion),
		"Consistency":  string(req.Consistency),
	})

	// ─── Phase 1: Validate Data Residency ────────────────────────────────────
	progress.Phase = "validating_residency"

	targetRegions := filterByResidency(req.TargetRegions, req.DataResidency)
	if len(targetRegions) == 0 {
		return nil, fmt.Errorf("no valid target regions after data residency filtering")
	}

	// ─── Phase 2: Check Region Health ────────────────────────────────────────
	progress.Phase = "checking_health"

	healthCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		StartToCloseTimeout: 10 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 2,
		},
	})

	var healthResults map[Region]RegionHealth
	err := workflow.ExecuteActivity(healthCtx, CheckAllRegionHealth, targetRegions).Get(ctx, &healthResults)
	if err != nil {
		logger.Warn("Health check failed, proceeding with all regions", "error", err)
		// Don't fail - proceed and let individual replications handle failures
	} else {
		// Remove offline regions
		var healthyRegions []Region
		for _, r := range targetRegions {
			if h, ok := healthResults[r]; ok && h.Status != "offline" {
				healthyRegions = append(healthyRegions, r)
			} else {
				progress.RegionStatuses[r] = "skipped_offline"
				logger.Warn("Skipping offline region", "region", r)
			}
		}
		targetRegions = healthyRegions
	}

	// ─── Phase 3: Replicate Based on Consistency Level ───────────────────────
	progress.Phase = "replicating"

	result := &ReplicationResult{
		EntityID:      req.Entity.EntityID,
		SourceRegion:  req.Entity.SourceRegion,
		Consistency:   req.Consistency,
		RegionResults: make(map[Region]RegionSyncResult),
	}

	switch req.Consistency {
	case ConsistencyStrong:
		err = replicateStrong(ctx, req, targetRegions, result, progress)
	case ConsistencyCausal:
		err = replicateCausal(ctx, req, targetRegions, result, progress)
	case ConsistencyEventual:
		err = replicateEventual(ctx, req, targetRegions, result, progress)
	default:
		err = replicateEventual(ctx, req, targetRegions, result, progress)
	}

	if err != nil {
		progress.Phase = "failed"
		return result, err
	}

	// ─── Phase 4: Verify Consistency ─────────────────────────────────────────
	if req.Consistency == ConsistencyStrong {
		progress.Phase = "verifying"

		verifyCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
			StartToCloseTimeout: 30 * time.Second,
			RetryPolicy: &temporal.RetryPolicy{
				MaximumAttempts: 3,
				InitialInterval: 2 * time.Second,
			},
		})

		var consistent bool
		err = workflow.ExecuteActivity(verifyCtx, VerifyConsistency, req.Entity.EntityID, targetRegions).Get(ctx, &consistent)
		if err != nil || !consistent {
			logger.Error("Consistency verification failed", "error", err, "consistent", consistent)
			// Trigger repair workflow
			repairCtx := workflow.WithChildOptions(ctx, workflow.ChildWorkflowOptions{
				WorkflowID: fmt.Sprintf("repair-%s-%d", req.Entity.EntityID, workflow.Now(ctx).Unix()),
			})
			_ = workflow.ExecuteChildWorkflow(repairCtx, ConsistencyRepairWorkflow, req.Entity, targetRegions).Get(ctx, nil)
		}
	}

	// Finalize
	result.TotalLatency = workflow.Now(ctx).Sub(startTime)
	result.Success = countSuccessful(result.RegionResults) >= quorumSize(len(targetRegions), req.Consistency)

	progress.Phase = "completed"
	logger.Info("Replication completed",
		"entity_id", req.Entity.EntityID,
		"latency", result.TotalLatency,
		"success", result.Success,
		"conflicts", result.ConflictsFound,
	)

	return result, nil
}

// ─────────────────────────────────────────────────────────────────────────────
// Replication Strategies
// ─────────────────────────────────────────────────────────────────────────────

// Strong: Write to quorum of regions synchronously
func replicateStrong(ctx workflow.Context, req ReplicationRequest, regions []Region, result *ReplicationResult, progress *ReplicationProgress) error {
	quorum := quorumSize(len(regions), ConsistencyStrong)

	ao := workflow.ActivityOptions{
		StartToCloseTimeout: 30 * time.Second, // Cross-region timeout
		HeartbeatTimeout:    10 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 3,
			InitialInterval: 1 * time.Second,
		},
		TaskQueue: "replication-tq", // Use region-aware routing below
	}

	// Fan-out to all regions simultaneously
	var futures []workflow.Future
	for _, region := range regions {
		regionCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
			StartToCloseTimeout: ao.StartToCloseTimeout,
			HeartbeatTimeout:    ao.HeartbeatTimeout,
			RetryPolicy:         ao.RetryPolicy,
			TaskQueue:           getRegionTaskQueue(region),
		})
		future := workflow.ExecuteActivity(regionCtx, WriteToRegion, req.Entity, region)
		futures = append(futures, future)
	}

	// Wait for quorum
	successCount := 0
	failCount := 0
	for i, future := range futures {
		var syncResult RegionSyncResult
		if err := future.Get(ctx, &syncResult); err != nil {
			syncResult = RegionSyncResult{
				Region:  regions[i],
				Success: false,
				Error:   err.Error(),
			}
			failCount++
		} else {
			successCount++
		}
		result.RegionResults[regions[i]] = syncResult
		progress.RegionStatuses[regions[i]] = statusFromResult(syncResult)
	}

	if successCount < quorum {
		return fmt.Errorf("quorum not reached: %d/%d succeeded (need %d)", successCount, len(regions), quorum)
	}

	return nil
}

// Causal: Write with vector clock, detect conflicts
func replicateCausal(ctx workflow.Context, req ReplicationRequest, regions []Region, result *ReplicationResult, progress *ReplicationProgress) error {
	// First, read current versions from all regions to detect conflicts
	readCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		StartToCloseTimeout: 10 * time.Second,
		RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 2},
	})

	var currentVersions map[Region]DataEntity
	err := workflow.ExecuteActivity(readCtx, ReadFromAllRegions, req.Entity.EntityID, regions).Get(ctx, &currentVersions)
	if err != nil {
		// If we can't read, fall back to eventual consistency
		return replicateEventual(ctx, req, regions, result, progress)
	}

	// Detect conflicts using vector clocks
	conflicts := detectConflicts(req.Entity, currentVersions)
	result.ConflictsFound = len(conflicts)

	if len(conflicts) > 0 {
		progress.Phase = "resolving_conflicts"
		progress.Conflicts = conflicts

		// Resolve conflicts
		for i, conflict := range conflicts {
			resolved, err := resolveConflict(ctx, conflict, req.ConflictStrategy)
			if err != nil {
				return fmt.Errorf("conflict resolution failed: %w", err)
			}
			conflicts[i] = *resolved
			// Update entity with resolved value
			req.Entity = resolved.VersionA // Use resolved version
		}
	}

	// Increment vector clock for source region
	if req.Entity.VectorClock == nil {
		req.Entity.VectorClock = make(map[Region]int64)
	}
	req.Entity.VectorClock[req.Entity.SourceRegion]++

	// Now replicate (eventually) with updated vector clock
	return replicateEventual(ctx, req, regions, result, progress)
}

// Eventual: Fire-and-forget to all regions (with retries)
func replicateEventual(ctx workflow.Context, req ReplicationRequest, regions []Region, result *ReplicationResult, progress *ReplicationProgress) error {
	// Fan-out to all regions - don't wait for all to succeed
	var futures []workflow.Future
	for _, region := range regions {
		ao := workflow.ActivityOptions{
			StartToCloseTimeout: 30 * time.Second,
			HeartbeatTimeout:    10 * time.Second,
			RetryPolicy: &temporal.RetryPolicy{
				InitialInterval:    2 * time.Second,
				BackoffCoefficient: 2.0,
				MaximumInterval:    1 * time.Minute,
				MaximumAttempts:    10, // More retries for eventual
			},
			TaskQueue: getRegionTaskQueue(region),
		}
		regionCtx := workflow.WithActivityOptions(ctx, ao)
		future := workflow.ExecuteActivity(regionCtx, WriteToRegion, req.Entity, region)
		futures = append(futures, future)
	}

	// Collect results (best effort)
	for i, future := range futures {
		var syncResult RegionSyncResult
		if err := future.Get(ctx, &syncResult); err != nil {
			syncResult = RegionSyncResult{
				Region:  regions[i],
				Success: false,
				Error:   err.Error(),
			}
		}
		result.RegionResults[regions[i]] = syncResult
		progress.RegionStatuses[regions[i]] = statusFromResult(syncResult)
	}

	return nil
}

// ─────────────────────────────────────────────────────────────────────────────
// Conflict Resolution Workflow
// ─────────────────────────────────────────────────────────────────────────────

func resolveConflict(ctx workflow.Context, conflict Conflict, strategy ConflictStrategy) (*Conflict, error) {
	switch strategy {
	case ConflictLastWriterWins:
		// Simple: pick the version with the latest timestamp
		if conflict.VersionA.UpdatedAt.After(conflict.VersionB.UpdatedAt) {
			conflict.Resolution = "version_a_wins"
		} else {
			conflict.Resolution = "version_b_wins"
			conflict.VersionA = conflict.VersionB // Swap to winner
		}
		conflict.ResolvedBy = "system"
		conflict.ResolvedAt = workflow.Now(ctx)
		return &conflict, nil

	case ConflictMerge:
		// Application-specific merge (e.g., CRDT-style)
		ao := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
			StartToCloseTimeout: 30 * time.Second,
		})
		var merged DataEntity
		err := workflow.ExecuteActivity(ao, MergeEntities, conflict.VersionA, conflict.VersionB).Get(ctx, &merged)
		if err != nil {
			return nil, err
		}
		conflict.VersionA = merged
		conflict.Resolution = "merged"
		conflict.ResolvedBy = "system"
		conflict.ResolvedAt = workflow.Now(ctx)
		return &conflict, nil

	case ConflictHumanResolve:
		// Wait for human to resolve via signal
		ao := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
			StartToCloseTimeout: 10 * time.Second,
		})
		_ = workflow.ExecuteActivity(ao, NotifyConflict, conflict).Get(ctx, nil)

		// Wait for resolution signal (timeout after 1 hour)
		signalCh := workflow.GetSignalChannel(ctx, "conflict_resolution")
		timerFuture := workflow.NewTimer(ctx, 1*time.Hour)

		selector := workflow.NewSelector(ctx)
		var resolution string
		var received bool

		selector.AddReceive(signalCh, func(ch workflow.ReceiveChannel, more bool) {
			ch.Receive(ctx, &resolution)
			received = true
		})
		selector.AddFuture(timerFuture, func(f workflow.Future) {
			_ = f.Get(ctx, nil)
		})
		selector.Select(ctx)

		if !received {
			// Fall back to last-writer-wins
			if conflict.VersionA.UpdatedAt.After(conflict.VersionB.UpdatedAt) {
				conflict.Resolution = "version_a_wins (timeout fallback)"
			} else {
				conflict.Resolution = "version_b_wins (timeout fallback)"
				conflict.VersionA = conflict.VersionB
			}
		} else {
			conflict.Resolution = resolution
			conflict.ResolvedBy = "human"
		}
		conflict.ResolvedAt = workflow.Now(ctx)
		return &conflict, nil

	default:
		// Default to last-writer-wins
		return resolveConflict(ctx, conflict, ConflictLastWriterWins)
	}
}

// ─────────────────────────────────────────────────────────────────────────────
// Consistency Repair Workflow
// ─────────────────────────────────────────────────────────────────────────────

func ConsistencyRepairWorkflow(ctx workflow.Context, entity DataEntity, regions []Region) error {
	logger := workflow.GetLogger(ctx)
	logger.Info("Starting consistency repair", "entity_id", entity.EntityID)

	ao := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		StartToCloseTimeout: 30 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 5,
			InitialInterval: 5 * time.Second,
		},
	})

	// Read from all regions
	var versions map[Region]DataEntity
	err := workflow.ExecuteActivity(ao, ReadFromAllRegions, entity.EntityID, regions).Get(ctx, &versions)
	if err != nil {
		return fmt.Errorf("failed to read all regions: %w", err)
	}

	// Find the authoritative version (highest vector clock sum or latest timestamp)
	authoritative := findAuthoritativeVersion(versions)

	// Write authoritative version to all regions that are behind
	for region, version := range versions {
		if version.Version < authoritative.Version || version.Checksum != authoritative.Checksum {
			logger.Info("Repairing region",
				"region", region,
				"current_version", version.Version,
				"target_version", authoritative.Version,
			)

			regionCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
				StartToCloseTimeout: 30 * time.Second,
				TaskQueue:           getRegionTaskQueue(region),
				RetryPolicy: &temporal.RetryPolicy{
					MaximumAttempts: 5,
				},
			})

			var result RegionSyncResult
			err := workflow.ExecuteActivity(regionCtx, WriteToRegion, authoritative, region).Get(ctx, &result)
			if err != nil {
				logger.Error("Repair failed for region", "region", region, "error", err)
			}
		}
	}

	return nil
}

// ─────────────────────────────────────────────────────────────────────────────
// Region Failover Workflow
// ─────────────────────────────────────────────────────────────────────────────

func RegionFailoverWorkflow(ctx workflow.Context, req FailoverRequest) error {
	logger := workflow.GetLogger(ctx)
	logger.Info("Starting region failover",
		"failed_region", req.FailedRegion,
		"target_region", req.TargetRegion,
		"reason", req.Reason,
	)

	ao := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		StartToCloseTimeout: 5 * time.Minute,
		HeartbeatTimeout:    30 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 3,
		},
	})

	// Step 1: Verify the region is actually down
	var health RegionHealth
	err := workflow.ExecuteActivity(ao, CheckRegionHealth, req.FailedRegion).Get(ctx, &health)
	if err == nil && health.Healthy {
		logger.Info("Region is actually healthy, aborting failover")
		return nil
	}

	// Step 2: Update DNS to route traffic away from failed region
	err = workflow.ExecuteActivity(ao, UpdateDNSRouting, req.FailedRegion, req.TargetRegion).Get(ctx, nil)
	if err != nil {
		return fmt.Errorf("DNS update failed: %w", err)
	}

	// Step 3: Promote standby Temporal cluster (if using active-passive)
	err = workflow.ExecuteActivity(ao, PromoteTemporalCluster, req.TargetRegion).Get(ctx, nil)
	if err != nil {
		logger.Error("Temporal cluster promotion failed", "error", err)
		// Non-fatal: may already be active-active
	}

	// Step 4: Verify target region is handling traffic
	_ = workflow.Sleep(ctx, 30*time.Second)

	var targetHealth RegionHealth
	err = workflow.ExecuteActivity(ao, CheckRegionHealth, req.TargetRegion).Get(ctx, &targetHealth)
	if err != nil || !targetHealth.Healthy {
		return fmt.Errorf("target region not healthy after failover: %w", err)
	}

	// Step 5: Notify operations team
	err = workflow.ExecuteActivity(ao, SendFailoverNotification, req).Get(ctx, nil)
	if err != nil {
		logger.Warn("Notification failed", "error", err)
	}

	logger.Info("Failover completed successfully",
		"failed_region", req.FailedRegion,
		"target_region", req.TargetRegion,
	)

	return nil
}

// ─────────────────────────────────────────────────────────────────────────────
// Scheduled Consistency Verification Workflow
// ─────────────────────────────────────────────────────────────────────────────

type ConsistencyReport struct {
	CheckedAt      time.Time                `json:"checked_at"`
	EntitiesChecked int                     `json:"entities_checked"`
	Inconsistencies int                     `json:"inconsistencies"`
	Details        []InconsistencyDetail    `json:"details"`
	RepairedCount  int                      `json:"repaired_count"`
}

type InconsistencyDetail struct {
	EntityID    string            `json:"entity_id"`
	Regions     map[Region]string `json:"region_checksums"` // region -> checksum
	RepairStatus string           `json:"repair_status"`
}

func ScheduledConsistencyCheckWorkflow(ctx workflow.Context, entityType string, sampleSize int) (*ConsistencyReport, error) {
	logger := workflow.GetLogger(ctx)

	ao := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		StartToCloseTimeout: 10 * time.Minute,
		HeartbeatTimeout:    30 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 3,
		},
	})

	// Sample random entities to check
	var entityIDs []string
	err := workflow.ExecuteActivity(ao, SampleEntityIDs, entityType, sampleSize).Get(ctx, &entityIDs)
	if err != nil {
		return nil, fmt.Errorf("failed to sample entities: %w", err)
	}

	report := &ConsistencyReport{
		CheckedAt:       workflow.Now(ctx),
		EntitiesChecked: len(entityIDs),
	}

	for _, entityID := range entityIDs {
		// Read from all regions and compare checksums
		var versions map[Region]DataEntity
		err := workflow.ExecuteActivity(ao, ReadFromAllRegions, entityID, AllRegions).Get(ctx, &versions)
		if err != nil {
			continue
		}

		// Check if all regions have the same checksum
		checksums := make(map[Region]string)
		var firstChecksum string
		consistent := true
		for region, entity := range versions {
			checksums[region] = entity.Checksum
			if firstChecksum == "" {
				firstChecksum = entity.Checksum
			} else if entity.Checksum != firstChecksum {
				consistent = false
			}
		}

		if !consistent {
			report.Inconsistencies++
			detail := InconsistencyDetail{
				EntityID: entityID,
				Regions:  checksums,
			}

			// Auto-repair
			entity := findAuthoritativeVersion(versions)
			childCtx := workflow.WithChildOptions(ctx, workflow.ChildWorkflowOptions{
				WorkflowID: fmt.Sprintf("repair-%s-%d", entityID, workflow.Now(ctx).Unix()),
			})
			err := workflow.ExecuteChildWorkflow(childCtx, ConsistencyRepairWorkflow, entity, AllRegions).Get(ctx, nil)
			if err != nil {
				detail.RepairStatus = "failed"
				logger.Error("Auto-repair failed", "entity_id", entityID, "error", err)
			} else {
				detail.RepairStatus = "repaired"
				report.RepairedCount++
			}

			report.Details = append(report.Details, detail)
		}
	}

	logger.Info("Consistency check completed",
		"checked", report.EntitiesChecked,
		"inconsistencies", report.Inconsistencies,
		"repaired", report.RepairedCount,
	)

	return report, nil
}

// ─────────────────────────────────────────────────────────────────────────────
// Region Health Monitor (Long-Running)
// ─────────────────────────────────────────────────────────────────────────────

func RegionHealthMonitorWorkflow(ctx workflow.Context) error {
	logger := workflow.GetLogger(ctx)

	ao := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		StartToCloseTimeout: 10 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 2,
		},
	})

	consecutiveFailures := make(map[Region]int)
	const failoverThreshold = 3 // 3 consecutive failures = failover

	iteration := 0
	for {
		// Check every 30 seconds
		_ = workflow.Sleep(ctx, 30*time.Second)
		iteration++

		for _, region := range AllRegions {
			var health RegionHealth
			err := workflow.ExecuteActivity(ao, CheckRegionHealth, region).Get(ctx, &health)

			if err != nil || !health.Healthy {
				consecutiveFailures[region]++
				logger.Warn("Region unhealthy",
					"region", region,
					"consecutive_failures", consecutiveFailures[region],
				)

				if consecutiveFailures[region] >= failoverThreshold {
					// Trigger automatic failover
					targetRegion := selectFailoverTarget(region)
					childCtx := workflow.WithChildOptions(ctx, workflow.ChildWorkflowOptions{
						WorkflowID: fmt.Sprintf("failover-%s-%d", region, workflow.Now(ctx).Unix()),
					})
					_ = workflow.ExecuteChildWorkflow(childCtx, RegionFailoverWorkflow, FailoverRequest{
						FailedRegion: region,
						TargetRegion: targetRegion,
						Reason:       fmt.Sprintf("auto-failover after %d consecutive failures", consecutiveFailures[region]),
						Automatic:    true,
					}).Get(ctx, nil)

					consecutiveFailures[region] = 0
				}
			} else {
				consecutiveFailures[region] = 0
			}
		}

		// Continue-as-new every 1000 iterations to bound history
		if iteration >= 1000 {
			return workflow.NewContinueAsNewError(ctx, RegionHealthMonitorWorkflow)
		}
	}
}

// ─────────────────────────────────────────────────────────────────────────────
// Activities
// ─────────────────────────────────────────────────────────────────────────────

type ReplicationActivities struct {
	RegionClients map[Region]RegionClient
}

type RegionClient interface {
	Read(ctx context.Context, entityID string) (*DataEntity, error)
	Write(ctx context.Context, entity DataEntity) error
	HealthCheck(ctx context.Context) (*RegionHealth, error)
}

func (a *ReplicationActivities) WriteToRegion(ctx context.Context, entity DataEntity, region Region) (*RegionSyncResult, error) {
	start := time.Now()
	activity.RecordHeartbeat(ctx, fmt.Sprintf("writing to %s", region))

	client, ok := a.RegionClients[region]
	if !ok {
		return nil, fmt.Errorf("no client for region %s", region)
	}

	err := client.Write(ctx, entity)
	latency := time.Since(start)

	if err != nil {
		return &RegionSyncResult{
			Region:  region,
			Success: false,
			Latency: latency,
			Error:   err.Error(),
		}, temporal.NewApplicationError(err.Error(), "WriteError")
	}

	return &RegionSyncResult{
		Region:  region,
		Success: true,
		Latency: latency,
		Version: entity.Version,
	}, nil
}

func (a *ReplicationActivities) ReadFromAllRegions(ctx context.Context, entityID string, regions []Region) (map[Region]DataEntity, error) {
	results := make(map[Region]DataEntity)
	var mu sync.Mutex
	var wg sync.WaitGroup

	for _, region := range regions {
		wg.Add(1)
		go func(r Region) {
			defer wg.Done()
			activity.RecordHeartbeat(ctx, fmt.Sprintf("reading from %s", r))

			client, ok := a.RegionClients[r]
			if !ok {
				return
			}

			entity, err := client.Read(ctx, entityID)
			if err != nil {
				return
			}

			mu.Lock()
			results[r] = *entity
			mu.Unlock()
		}(region)
	}

	wg.Wait()
	return results, nil
}

func (a *ReplicationActivities) CheckRegionHealth(ctx context.Context, region Region) (*RegionHealth, error) {
	client, ok := a.RegionClients[region]
	if !ok {
		return &RegionHealth{Region: region, Healthy: false, Status: "no_client"}, nil
	}

	health, err := client.HealthCheck(ctx)
	if err != nil {
		return &RegionHealth{
			Region:      region,
			Healthy:     false,
			Status:      "unreachable",
			LastChecked: time.Now(),
		}, nil
	}

	return health, nil
}

func (a *ReplicationActivities) CheckAllRegionHealth(ctx context.Context, regions []Region) (map[Region]RegionHealth, error) {
	results := make(map[Region]RegionHealth)
	for _, region := range regions {
		health, _ := a.CheckRegionHealth(ctx, region)
		if health != nil {
			results[region] = *health
		}
	}
	return results, nil
}

func (a *ReplicationActivities) VerifyConsistency(ctx context.Context, entityID string, regions []Region) (bool, error) {
	versions, err := a.ReadFromAllRegions(ctx, entityID, regions)
	if err != nil {
		return false, err
	}

	var firstChecksum string
	for _, entity := range versions {
		if firstChecksum == "" {
			firstChecksum = entity.Checksum
		} else if entity.Checksum != firstChecksum {
			return false, nil
		}
	}
	return true, nil
}

func (a *ReplicationActivities) MergeEntities(ctx context.Context, a1, b DataEntity) (*DataEntity, error) {
	// Application-specific merge logic
	// For example: merge JSON objects, taking non-null fields from both
	merged := a1
	if a1.UpdatedAt.Before(b.UpdatedAt) {
		merged.Data = b.Data
		merged.UpdatedAt = b.UpdatedAt
	}
	merged.Version = max(a1.Version, b.Version) + 1
	merged.Checksum = computeChecksum(merged.Data)
	return &merged, nil
}

func (a *ReplicationActivities) UpdateDNSRouting(ctx context.Context, failedRegion, targetRegion Region) error {
	activity.RecordHeartbeat(ctx, "updating DNS routing")
	// Update Route53 / CloudFlare to route traffic away from failed region
	return nil
}

func (a *ReplicationActivities) PromoteTemporalCluster(ctx context.Context, region Region) error {
	activity.RecordHeartbeat(ctx, "promoting temporal cluster")
	// tctl cluster promote --region ...
	return nil
}

func (a *ReplicationActivities) SendFailoverNotification(ctx context.Context, req FailoverRequest) error {
	return nil
}

func (a *ReplicationActivities) NotifyConflict(ctx context.Context, conflict Conflict) error {
	return nil
}

func (a *ReplicationActivities) SampleEntityIDs(ctx context.Context, entityType string, sampleSize int) ([]string, error) {
	// SELECT id FROM entities WHERE type = $1 ORDER BY RANDOM() LIMIT $2
	ids := make([]string, sampleSize)
	for i := range ids {
		ids[i] = fmt.Sprintf("entity-%d", i)
	}
	return ids, nil
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper Functions
// ─────────────────────────────────────────────────────────────────────────────

func getRegionTaskQueue(region Region) string {
	return fmt.Sprintf("replication-%s-tq", region)
}

func filterByResidency(regions []Region, rules []DataResidencyRule) []Region {
	if len(rules) == 0 {
		return regions
	}

	allowed := make(map[Region]bool)
	for _, r := range regions {
		allowed[r] = true
	}

	for _, rule := range rules {
		// Remove prohibited regions
		for _, prohibited := range rule.ProhibitedRegions {
			delete(allowed, prohibited)
		}
		// If allowed list specified, only keep those
		if len(rule.AllowedRegions) > 0 {
			for r := range allowed {
				found := false
				for _, a := range rule.AllowedRegions {
					if r == a {
						found = true
						break
					}
				}
				if !found {
					delete(allowed, r)
				}
			}
		}
	}

	var result []Region
	for r := range allowed {
		result = append(result, r)
	}
	return result
}

func quorumSize(total int, consistency ConsistencyLevel) int {
	switch consistency {
	case ConsistencyStrong:
		return (total / 2) + 1 // Majority quorum
	case ConsistencyCausal:
		return 1 // At least one
	case ConsistencyEventual:
		return 0 // Best effort
	default:
		return 1
	}
}

func countSuccessful(results map[Region]RegionSyncResult) int {
	count := 0
	for _, r := range results {
		if r.Success {
			count++
		}
	}
	return count
}

func statusFromResult(r RegionSyncResult) string {
	if r.Success {
		return "replicated"
	}
	return "failed"
}

func detectConflicts(incoming DataEntity, current map[Region]DataEntity) []Conflict {
	var conflicts []Conflict
	for region, existing := range current {
		if region == incoming.SourceRegion {
			continue
		}
		// Conflict: existing version is different and not causally related
		if existing.Checksum != incoming.Checksum && !isCausallyRelated(incoming.VectorClock, existing.VectorClock) {
			conflicts = append(conflicts, Conflict{
				EntityID:   incoming.EntityID,
				RegionA:    incoming.SourceRegion,
				RegionB:    region,
				VersionA:   incoming,
				VersionB:   existing,
				DetectedAt: time.Now(),
			})
		}
	}
	return conflicts
}

func isCausallyRelated(clockA, clockB map[Region]int64) bool {
	// A causally precedes B if all entries in A <= corresponding entries in B
	for region, countA := range clockA {
		if countB, ok := clockB[region]; !ok || countA > countB {
			return false
		}
	}
	return true
}

func findAuthoritativeVersion(versions map[Region]DataEntity) DataEntity {
	var best DataEntity
	for _, v := range versions {
		if v.Version > best.Version || (v.Version == best.Version && v.UpdatedAt.After(best.UpdatedAt)) {
			best = v
		}
	}
	return best
}

func selectFailoverTarget(failedRegion Region) Region {
	// Select geographically closest healthy region
	proximity := map[Region][]Region{
		RegionUSEast: {RegionUSWest, RegionEU, RegionLATAM, RegionAPAC},
		RegionUSWest: {RegionUSEast, RegionAPAC, RegionLATAM, RegionEU},
		RegionEU:     {RegionUSEast, RegionLATAM, RegionAPAC, RegionUSWest},
		RegionAPAC:   {RegionUSWest, RegionEU, RegionUSEast, RegionLATAM},
		RegionLATAM:  {RegionUSEast, RegionUSWest, RegionEU, RegionAPAC},
	}

	candidates := proximity[failedRegion]
	if len(candidates) > 0 {
		return candidates[0]
	}
	return RegionUSEast // Fallback
}

func computeChecksum(data []byte) string {
	hash := sha256.Sum256(data)
	return hex.EncodeToString(hash[:])
}

func max(a, b int64) int64 {
	if a > b {
		return a
	}
	return b
}
```

## Worker Setup (Per Region)

```go
package main

import (
	"log"
	"os"
	"time"

	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"

	replication "mycompany/data-replication"
)

func main() {
	region := os.Getenv("REGION") // e.g., "us-east-1"

	c, err := client.Dial(client.Options{
		HostPort:  os.Getenv("TEMPORAL_HOST"), // Regional Temporal endpoint
		Namespace: "replication",
	})
	if err != nil {
		log.Fatalf("Unable to create client: %v", err)
	}
	defer c.Close()

	taskQueue := fmt.Sprintf("replication-%s-tq", region)

	w := worker.New(c, taskQueue, worker.Options{
		MaxConcurrentActivityExecutionSize:     20,
		MaxConcurrentWorkflowTaskExecutionSize: 50,
		WorkerStopTimeout:                      30 * time.Second,
	})

	// Register all workflows
	w.RegisterWorkflow(replication.DataReplicationWorkflow)
	w.RegisterWorkflow(replication.ConsistencyRepairWorkflow)
	w.RegisterWorkflow(replication.RegionFailoverWorkflow)
	w.RegisterWorkflow(replication.ScheduledConsistencyCheckWorkflow)
	w.RegisterWorkflow(replication.RegionHealthMonitorWorkflow)

	// Register activities with region-specific clients
	activities := &replication.ReplicationActivities{
		RegionClients: initRegionClients(),
	}
	w.RegisterActivity(activities)

	if err := w.Run(worker.InterruptCh()); err != nil {
		log.Fatalf("Worker failed: %v", err)
	}
}
```

## Failure Scenarios & Handling

### 1. Region Goes Completely Offline

```
Scenario: ap-southeast-1 loses all connectivity
Detection: RegionHealthMonitorWorkflow detects 3 consecutive health check failures
Handling:
  1. Health monitor triggers RegionFailoverWorkflow
  2. DNS routing updated (Route53 health check removes region)
  3. In-flight replication activities to that region will timeout
  4. Temporal retries route to next-closest region
  5. Once region recovers: consistency repair workflow runs

Timeline:
  T+0s:   Region goes offline
  T+30s:  First health check failure detected
  T+60s:  Second failure
  T+90s:  Third failure → failover triggered
  T+120s: DNS propagated, traffic shifted
  T+150s: Failover complete, operations notified
  
Total impact: ~2.5 minutes (within 99.999% SLA budget)
```

### 2. Network Partition (Split-Brain)

```
Scenario: US-East and EU can't communicate, both accept writes
Detection: Replication activities fail between partitioned regions
Handling:
  1. Each region continues accepting writes locally (availability > consistency)
  2. Writes are queued for replication (Temporal retries with backoff)
  3. When partition heals, conflict detection runs
  4. Vector clocks identify concurrent writes
  5. Conflict resolution strategy applied (LWW, merge, or human)
  6. Resolved state replicated to all regions

Key insight: Temporal's retry policy with MaximumAttempts=10 and long intervals 
means replication attempts continue for hours without manual intervention.
```

### 3. Replication Lag Exceeds SLA

```
Scenario: EU region consistently 500ms+ behind US-East (SLA: 200ms)
Detection: RegionHealth.ReplicationLag metric
Handling:
  1. Increase worker concurrency for that region's task queue
  2. Check for network issues between regions
  3. If data volume spike: temporarily batch replications
  4. Alert if lag persists > 5 minutes
  5. Consider upgrading network tier (AWS Direct Connect)

Monitoring:
  - temporal_activity_execution_latency{task_queue="replication-eu-west-1-tq"}
  - custom metric: replication_lag_seconds{source="us-east-1", target="eu-west-1"}
```

### 4. Conflict During Concurrent Writes

```
Scenario: User updates profile in US-East, support agent updates in EU simultaneously
Detection: Vector clock comparison shows neither causally precedes the other
Handling (by strategy):
  - Last-Writer-Wins: Compare timestamps, later write wins
  - Merge: Deep merge JSON (non-null fields from both)
  - Application logic: domain-specific rules (e.g., support agent always wins)
  - Human: Notify support team, wait for manual resolution (1h timeout → LWW)
  
In Temporal:
  - Conflict detected during replicateCausal()
  - resolveConflict() called with configured strategy
  - Resolved version written to ALL regions (consistency repair)
```

### 5. DNS Failover During Active Workflows

```
Scenario: DNS shifts traffic mid-workflow (Temporal workflows are running)
Impact: Workflows on the failed region's Temporal cluster become inaccessible
Handling:
  - Temporal Multi-Cluster Replication: workflows are replicated across clusters
  - After failover, workflows resume on the new active cluster
  - No workflow state loss (replicated in real-time)
  - Activities in-flight will timeout and be retried on new cluster

Configuration:
  - Temporal cluster replication lag < 5s
  - Workflow history replicated synchronously to at least one standby
  - Namespace configured for automatic failover
```

### 6. Data Corruption Detection and Repair

```
Scenario: Bit rot or software bug corrupts data in one region
Detection: ScheduledConsistencyCheckWorkflow runs every hour, compares checksums
Handling:
  1. Checksum mismatch detected across regions
  2. Identify which region(s) have the corrupted copy
  3. Find authoritative version (highest version + most recent)
  4. ConsistencyRepairWorkflow overwrites corrupted copies
  5. Alert: investigate root cause of corruption

Prevention:
  - Entity checksums computed on write (SHA-256)
  - Checksums verified on read (detect corruption early)
  - Consistency checks sample 1% of entities per hour
```

## Production Configuration

```yaml
# Temporal Multi-Cluster Configuration
# Each region runs its own Temporal cluster with cross-cluster replication

# Primary cluster (us-east-1)
cluster:
  name: "us-east-1"
  rpc_address: "temporal-us-east-1.internal:7233"
  
  # Enable namespace replication
  replication:
    enabled: true
    clusters:
      - name: "us-east-1"
        rpc_address: "temporal-us-east-1.internal:7233"
        initial_failover_version: 1
      - name: "eu-west-1"
        rpc_address: "temporal-eu-west-1.internal:7233"
        initial_failover_version: 2
      - name: "ap-southeast-1"
        rpc_address: "temporal-ap-southeast-1.internal:7233"
        initial_failover_version: 3

# Namespace configuration
namespace:
  name: "replication"
  clusters: ["us-east-1", "eu-west-1", "ap-southeast-1"]
  active_cluster: "us-east-1"
  is_global_namespace: true
  failover_policy: "automatic"  # or "manual" for controlled failover
  retention: 30d

# Search attributes
search_attributes:
  EntityID: Keyword
  EntityType: Keyword
  SourceRegion: Keyword
  Consistency: Keyword
  
# Scheduled workflows
schedules:
  - id: consistency-check-hourly
    spec:
      intervals:
        - every: 1h
    action:
      workflow: ScheduledConsistencyCheckWorkflow
      args: ["all", 10000]  # Check 10K entities per hour

  - id: region-health-monitor
    # Long-running, not scheduled (started once)
    action:
      workflow: RegionHealthMonitorWorkflow

# Worker deployment per region
workers:
  us-east-1:
    replicas: 10
    task_queue: "replication-us-east-1-tq"
    max_concurrent_activities: 20
  eu-west-1:
    replicas: 8
    task_queue: "replication-eu-west-1-tq"
    max_concurrent_activities: 20
  ap-southeast-1:
    replicas: 6
    task_queue: "replication-ap-southeast-1-tq"
    max_concurrent_activities: 15
```

## Metrics & Observability

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `replication_latency_p99` | Cross-region write latency | > 500ms |
| `replication_lag_seconds` | Seconds behind primary | > 5s |
| `replication_conflicts_total` | Conflicts detected | > 10/min |
| `replication_failures_total` | Failed replications | > 1% |
| `region_health_status` | 1=healthy, 0=unhealthy | == 0 |
| `consistency_check_inconsistencies` | Found inconsistencies | > 0.1% |
| `failover_duration_seconds` | Time to complete failover | > 300s |
| `data_residency_violations` | Attempted writes to prohibited regions | > 0 |

## Data Sovereignty Enforcement

```go
// GDPR: EU user data must stay in EU
// Enforced at workflow level before replication

func enforceDataResidency(entity DataEntity, targetRegions []Region) []Region {
    classification := entity.Metadata["data_classification"]
    
    switch classification {
    case "eu_pii":
        // EU PII can only be stored in EU regions
        return filterRegions(targetRegions, []Region{RegionEU})
    case "us_financial":
        // US financial data must stay in US
        return filterRegions(targetRegions, []Region{RegionUSEast, RegionUSWest})
    default:
        return targetRegions
    }
}
```

## Key Design Decisions

1. **One workflow per entity replication** (not per region): Allows tracking complete replication lifecycle including conflict resolution.

2. **Region-specific task queues**: Workers in each region only process their region's activities, ensuring data locality and minimizing cross-region traffic.

3. **Vector clocks for causal consistency**: Enables correct conflict detection without global coordination.

4. **Separate health monitor workflow**: Decouples failure detection from replication. Continues running even when individual replications fail.

5. **Scheduled consistency checks**: Defense in depth - catches issues that escape real-time detection (bit rot, bugs, missed events).

6. **Automatic failover with manual override**: Health monitor auto-fails over after 3 failures, but operators can force failover/failback via signal.
