# Design Kubernetes-like scheduler - System Design Deep Dive

**Problem #84**  
**Category:** Infrastructure  
**Primary pattern:** control-plane scheduler + bin packing + watch-based reconciliation  
**Deep-dive focus:** bin packing, constraints, priorities, preemption, failures

## 0. Interview Framing

A Kubernetes-like scheduler places pending workloads onto a fleet of machines while respecting resource requests, affinity rules, taints/tolerations, quotas, priority, disruption constraints, and failure recovery. The scheduler does not run containers directly; it makes binding decisions and lets node agents/controllers converge actual state.

In an interview, anchor the design around the highest-risk path: **pending pod -> filter feasible nodes -> score/rank nodes -> reserve/assume resources -> bind -> reconcile**. Keep metrics, UI, long-term analytics, and cleanup asynchronous. The correctness boundary is the control-plane state store plus scheduler binding state, not an in-memory cache.

## 1. Requirements

### Functional Requirements

- Accept workload specs with CPU, memory, GPU, storage, image, priority, namespace, labels, affinity, anti-affinity, tolerations, and topology constraints.
- Maintain cluster inventory: nodes, allocatable resources, health, labels, taints, zones, capacity, and running workload assignments.
- Schedule pending workloads onto feasible nodes using filter and scoring plugins.
- Support priorities, preemption, fairness, quotas, and backoff for unschedulable workloads.
- Bind workloads atomically so two scheduler instances do not place the same workload twice.
- Watch cluster state changes and reschedule when nodes fail, resources change, or workloads terminate.
- Expose admin/debug APIs for scheduling traces, failed constraints, dry-run scheduling, replay, and policy changes.

### Non-Functional Requirements

- High availability for the control plane; scheduling should survive a scheduler instance crash.
- Low scheduling latency for normal workloads, with bounded queueing under bursts.
- No overcommit beyond configured policy for hard resources.
- Strong consistency for workload binding and scheduler leadership/fencing.
- Eventual consistency is acceptable for dashboards, metrics, search, and recommendation-style placement hints.
- Multi-tenant isolation by namespace, quota, priority class, and policy.
- Full audit trail for bindings, preemptions, policy changes, and privileged operations.

### Non-Goals

- Do not design the container runtime, image registry, service mesh, or CNI in depth.
- Do not make the scheduler responsible for actually starting containers; node agents own local execution.
- Do not require a global distributed transaction across all nodes.
- Do not keep the authoritative cluster state only in scheduler memory.

## 2. Capacity, Traffic, And Size Estimation

Use assumptions to size queue throughput, control-plane store writes, watch fanout, and scheduling cache memory.

| Dimension | Baseline Assumption |
|---|---:|
| Clusters | 1K large clusters or many smaller tenant clusters |
| Nodes per large cluster | 10K to 100K |
| Running pods per large cluster | 500K to 2M |
| Scheduling attempts | 5K/sec average, 50K/sec burst during rollout/autoscale |
| Watch consumers | schedulers, controllers, node agents, operators |
| Scheduling latency target | p95 < 1s for normal pods, p99 < 5s during bursts |
| State retention | live state in control-plane store; events/audit retained by policy |

### Estimation Formulas

- Pending queue memory = pending_pods x average_pod_spec_size x overhead.
- Scheduling cache memory = nodes x node_info_size + running_pods x compact_pod_info_size.
- Scheduling CPU = attempts/sec x average feasible-node evaluation cost.
- Store write QPS = pod creates + binds + status changes + node heartbeats + controller updates.
- Watch fanout = state changes/sec x watchers x average event size.
- Event log volume/day = scheduling_events/day x event_size x retention_factor.

### Sizing Notes

- Node heartbeats and pod status updates can dominate control-plane write load; keep scheduler watches filtered and compact.
- Avoid scanning all nodes for every pod at very large scale. Use precomputed indexes by label, zone, resource class, taint, GPU type, and topology.
- Separate authoritative state from scheduling cache. The cache is an optimization and must be reconstructable from the control-plane store.
- Model bursty rollouts separately from average scheduling load.

## 3. API Design

Use REST/gRPC for control-plane APIs and watch streams for state propagation. Every mutation includes idempotency or resource version semantics.

### Public / Control-Plane APIs

```http
POST /v1/namespaces/{namespace}/pods
Idempotency-Key: <uuid>
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "payments-worker-abc",
  "priority_class": "high",
  "resources": {"cpu_millis": 500, "memory_mb": 1024, "gpu": 0},
  "labels": {"app": "payments", "tier": "worker"},
  "constraints": {
    "node_selector": {"disk": "ssd"},
    "zone_spread": {"max_skew": 1},
    "anti_affinity": [{"label": "app", "value": "payments"}]
  }
}
```

```http
GET /v1/namespaces/{namespace}/pods/{pod_id}
Authorization: Bearer <token>
```

```http
POST /v1/pods/{pod_id}/binding
Idempotency-Key: <uuid>
Content-Type: application/json

{
  "node_id": "node_123",
  "scheduler_id": "sched_a",
  "expected_resource_version": "rv_456",
  "assumed_resources": {"cpu_millis": 500, "memory_mb": 1024}
}
```

```http
GET /v1/watch?resource=pods,nodes,bindings&resourceVersion=rv_123
Authorization: Bearer <token>
```

```http
POST /v1/scheduler/dry-run
Content-Type: application/json

{
  "pod_spec": {},
  "explain": true
}
```

### Internal APIs

```protobuf
service SchedulerService {
  rpc EnqueuePod(EnqueuePodRequest) returns (EnqueuePodResponse);
  rpc ScheduleNext(ScheduleNextRequest) returns (ScheduleDecision);
  rpc Bind(BindRequest) returns (BindResponse);
  rpc Explain(ExplainRequest) returns (SchedulingTrace);
}

service ClusterStateService {
  rpc Watch(WatchRequest) returns (stream ClusterEvent);
  rpc CompareAndSetBinding(BindRequest) returns (BindResult);
  rpc ListNodes(NodeQuery) returns (NodePage);
}
```

### Error Model

- `400`: invalid spec or unsupported constraint.
- `401/403`: missing identity, namespace denial, quota denial, or policy denial.
- `404`: pod/node not found or hidden by authorization.
- `409`: stale resource version, duplicate binding, or conflicting scheduler assumption.
- `422`: pod is valid but currently unschedulable.
- `429`: namespace, tenant, or API quota exceeded.
- `5xx`: dependency/control-plane failure; preserve retry-safe semantics and request ID.

## 4. Async Event Contracts

Use immutable scheduling events for debugging, audit, analytics, replay, and controller workflows. Partition events by cluster and pod ID when per-pod ordering matters.

```json
{
  "event_id": "evt_01H...",
  "event_type": "scheduler.pod_binding_decided.v1",
  "occurred_at": "2026-05-25T10:15:30Z",
  "cluster_id": "cluster_123",
  "namespace": "payments",
  "pod_id": "pod_123",
  "pod_version": "rv_456",
  "scheduler_id": "sched_a",
  "decision": {
    "node_id": "node_123",
    "score": 97,
    "filtered_nodes": 9200,
    "feasible_nodes": 348
  },
  "payload_ref": "object://scheduler-traces/evt_01H"
}
```

### Core Events

- `scheduler.pod_enqueued.v1`
- `scheduler.filter_failed.v1`
- `scheduler.pod_assumed.v1`
- `scheduler.pod_binding_decided.v1`
- `scheduler.pod_bound.v1`
- `scheduler.pod_unschedulable.v1`
- `scheduler.preemption_requested.v1`
- `scheduler.node_state_changed.v1`
- `scheduler.policy_updated.v1`

### Eventing Rules

- Scheduling events are immutable and replayable.
- Consumers are idempotent and track processed event IDs.
- Large traces and plugin explanations are stored as object references, not inline payloads.
- Schema changes are additive; breaking changes use new event versions.
- DLQs include owner, runbook, first failure, last failure, and replay command.

## 5. High-Level Architecture

### Architecture Design

```text
Kubernetes-like Scheduler Architecture

CLI / API Clients / Controllers / Autoscalers
        |
        v
API Server / AuthN / AuthZ / Admission / Quotas
        |
        v
Strongly Consistent Cluster State Store
        |
        +--> Watch Stream / Informer Cache
        |       -> Scheduler Instances
        |             -> Priority Queue / Backoff Queue
        |             -> Scheduling Cache
        |             -> Filter Plugins
        |             -> Score Plugins
        |             -> Preemption Engine
        |             -> Binder
        |
        +--> Controllers
        |       -> ReplicaSet / Job / StatefulSet / Node / Disruption Controllers
        |
        +--> Node Agents
        |       -> receive bound pods and run local containers
        |
        +--> Async Platform
                -> Scheduling Events / Audit / Metrics / Trace Store / Analytics

Data Stores:
  - CP cluster state store for pods, nodes, bindings, leases, policies, quotas.
  - Event log for scheduling decisions, audit, and replay.
  - Redis/local caches for non-authoritative scheduling indexes and queues.
  - Object storage for large traces, profiles, and long-retention audit exports.
  - TSDB/OLAP store for metrics and scheduling analytics.
```

### Request And Data Flow

1. **Pod creation:** API server authenticates the caller, applies admission policies, checks namespace quota, persists the pod in `Pending` state, and emits a watch event.
2. **Scheduler watch:** scheduler instances consume pod/node/resource updates and update their local scheduling cache.
3. **Queueing:** unscheduled pods enter an active priority queue or backoff queue based on priority, retry count, and unschedulable reason.
4. **Filtering:** scheduler filters nodes by hard constraints: resource fit, node selector, taints/tolerations, affinity, topology spread, volume constraints, and policy.
5. **Scoring:** scheduler scores feasible nodes by resource balance, locality, spread, utilization, affinity preferences, and custom plugins.
6. **Assume/reserve:** scheduler assumes resources in local cache to avoid repeatedly picking the same capacity while binding is pending.
7. **Binding:** binder performs compare-and-set against the authoritative state store using pod resource version and scheduler lease/fencing token.
8. **Convergence:** node agent observes the binding, starts the pod, reports status, and controllers reconcile desired versus actual state.

### Component Responsibilities

- **API Server**: owns request validation, auth, admission, quota checks, resource versioning, watch stream, and persistence into the cluster state store.
- **Cluster State Store**: owns authoritative pods, nodes, bindings, leases, policies, quotas, and resource versions.
- **Scheduler Queue**: owns pending pod ordering, priority, fairness, backoff, and requeue triggers.
- **Scheduling Cache**: owns reconstructed non-authoritative node/pod state optimized for filter/score plugins.
- **Filter Plugins**: reject nodes that violate hard constraints.
- **Score Plugins**: rank feasible nodes using soft preferences and policy weights.
- **Preemption Engine**: finds lower-priority victims when high-priority pods cannot be scheduled.
- **Binder**: commits the selected node atomically with resource version/fencing checks.
- **Node Agent**: runs bound pods, reports node/pod status, and enforces local resource isolation.
- **Controllers**: create desired workloads and repair drift; they do not choose final node placement.
- **Audit/Observability Pipeline**: stores scheduling traces, decisions, metrics, and operator actions.

### Service Responsibility Matrix

| Layer | Services | Responsibility |
| --- | --- | --- |
| API/control boundary | API server, auth, admission, quota | Validate and persist desired state with resource versions and policy decisions. |
| Authoritative data | Cluster state store | Strongly consistent source of truth for pod specs, node state, bindings, leases, quotas, and policies. |
| Scheduling engine | Queue, cache, filter, score, preemption, binder | Decide feasible placement and commit binding safely. |
| Execution plane | Node agents/runtime | Execute bound workloads locally and report actual state. |
| Reconciliation | Controllers/autoscalers | Create desired state, react to failures, and keep actual state converged. |
| Async data | Event log, metrics, trace store, warehouse | Debugging, replay, analytics, SLOs, and capacity planning. |
| Operations | Admin console, audit, runbooks | Explain decisions, replay safely, tune policies, and handle incidents. |

## 6. Low-Level Design

### Core Classes / Interfaces

```java
interface SchedulingPlugin {
  FilterResult filter(PodSpec pod, NodeInfo node, SchedulingContext ctx);
  ScoreResult score(PodSpec pod, NodeInfo node, SchedulingContext ctx);
}

interface ClusterStateRepository {
  WatchStream watch(ResourceVersion fromVersion);
  Pod getPod(PodId podId, ReadConsistency consistency);
  BindResult compareAndSetBinding(PodId podId, NodeId nodeId, ResourceVersion expectedVersion, FencingToken token);
}

final class SchedulingDecision {
  PodId podId;
  NodeId selectedNode;
  List<FilterFailure> rejectedReasons;
  Map<NodeId, Integer> scores;
  ResourceVersion podVersion;
}
```

### Important Algorithms And Data Structures

- Priority queue ordered by priority class, creation time, fairness bucket, and backoff deadline.
- Node indexes by label, taint, zone, capacity class, GPU type, storage topology, and health.
- Filter pipeline short-circuits hard failures before expensive scoring.
- Score pipeline normalizes plugin scores and applies configured weights.
- Assumed-pod cache reserves resources locally until binding succeeds or times out.
- Preemption simulates removing lower-priority pods and checks disruption budgets.
- Watch cache uses resource versions to recover from disconnects and replay missed updates.

### State Machines

```text
Pod: CREATED -> PENDING -> ASSUMED -> BINDING -> BOUND -> RUNNING -> SUCCEEDED/FAILED
                    |          |          |
                    |          |          -> BIND_FAILED -> BACKOFF -> PENDING
                    |          -> ASSUME_EXPIRED -> PENDING
                    -> UNSCHEDULABLE -> BACKOFF -> PENDING

Node: REGISTERED -> READY -> DRAINING -> NOT_READY -> DELETED
```

### Consistency Model

- Strong consistency for API-server writes, pod binding, scheduler leadership/fencing, quotas, and policy versions.
- Eventual consistency for scheduler local caches, metrics, dashboards, search, capacity reports, and trace analytics.
- Optimistic concurrency with resource versions for normal object updates.
- Leases/fencing tokens for scheduler leadership and binding ownership.
- Controllers converge actual state after node failure or watch lag.

## 7. Database Modeling And DB Design

### Core Tables

| Table / Collection | Important Columns |
|---|---|
| `clusters` | `id, tenant_id, region, version, state, created_at` |
| `namespaces` | `id, cluster_id, name, quota_spec, policy_ref, state` |
| `nodes` | `id, cluster_id, zone, labels_json, taints_json, allocatable_json, capacity_json, heartbeat_at, state, resource_version` |
| `pods` | `id, cluster_id, namespace_id, spec_ref, priority, state, assigned_node_id, resource_version, created_at, updated_at` |
| `pod_bindings` | `pod_id, node_id, scheduler_id, fencing_token, bound_at, resource_version` |
| `scheduler_leases` | `scheduler_id, cluster_id, holder_identity, fencing_token, expires_at, renewed_at` |
| `scheduling_queue` | `pod_id, priority, fairness_bucket, backoff_until, unschedulable_reason, attempt` |
| `scheduling_events` | `event_id, cluster_id, pod_id, event_type, decision_ref, created_at` |
| `policies` | `id, cluster_id, policy_type, body_json, version, state, updated_at` |
| `audit_log` | `audit_id, actor_id, action, resource_type, resource_id, before_hash, after_hash, reason, created_at` |

### Database Technology Choice

| Workload / Data | Recommended Database / Store | Why This Choice Fits |
| --- | --- | --- |
| Source of truth / primary store | etcd/Consul/ZooKeeper/Raft-backed KV, or CockroachDB/Spanner for a SQL-style implementation | scheduler binding, leases, resource versions, quotas, and policies require CP semantics and compare-and-set updates |
| Hot serving / cache | in-memory informer cache plus optional Redis for non-authoritative queues and indexes | filter/score cannot round-trip to the primary store for every node; cache is rebuilt from watches |
| Event stream / outbox | Kafka/Pulsar/Kinesis for scheduling events, audit fanout, metrics, and replay | decouples tracing, analytics, and capacity planning from binding latency |
| Search / analytics | OpenSearch for decision search; Prometheus/Mimir for metrics; ClickHouse/Druid/warehouse for scheduling analytics | debugging and fleet analytics should not overload the CP state store |
| Large immutable payloads | S3/GCS/Azure Blob/object storage for pod specs, scheduling traces, profiles, audit exports, and snapshots | large traces and historical evidence are cheaper and safer outside the control-plane store |

Interview stance: the control-plane state store is the source of truth. Scheduler caches, queue indexes, metrics, search, and warehouse tables are derived and must be rebuildable from resource versions, snapshots, and immutable events.

### Replication Strategy

- Primary store: use quorum replication across at least three control-plane nodes/AZs. A write is committed only after quorum acknowledgement.
- Scheduler instances: run multiple replicas, but only a fenced binding operation can commit a decision.
- Watch cache: each scheduler keeps local state and reconnects from the last resource version after disconnect.
- Event log: replicate partitions across brokers and retain scheduling events long enough for debugging and replay.
- Object storage and analytics: replicate for durability; rebuild analytical projections from events when correctness is uncertain.

### Sharding And Partitioning Strategy

- Primary partition key: `cluster_id`, then `namespace_id`, `pod_id`, or `node_id` depending on access pattern.
- Primary lookup path: `pod_id`, `node_id`, and `cluster_id + resource_version` should be efficient.
- Large environments should shard by cluster/cell. Avoid one global state store for every cluster.
- Time-partition append-heavy data such as `scheduling_events`, audit logs, traces, metrics, and queue history.
- Hot partition mitigation: split very large clusters into cells, shard scheduler queues by namespace/fairness bucket, and keep node indexes local to scheduler replicas.

### Indexing Strategy

- Required secondary indexes: `cluster_id + state`, `namespace_id + priority + created_at`, `assigned_node_id`, `state + backoff_until`, `scheduler_id + expires_at`, `node labels/taints` via precomputed indexes.
- Keep the CP store index set small; broad explanation/search queries go to OpenSearch or object-store traces.
- Use resource-version indexes for watch replay and consistent pagination.
- Index `(state, updated_at)` for repair jobs that find stuck pods, stale nodes, expired leases, and old assumed pods.
- Use compact append-only indexes for event/audit tables and time-bucketed partitions for retention.

### CAP Theorem And Consistency Choices

| Data / Operation | CAP Bias During Partition | Consistency Model | Interview Notes |
| --- | --- | --- | --- |
| Pod binding / leases / resource versions | CP | linearizable or serializable compare-and-set | Prefer refusing unsafe binds over split-brain double placement. |
| Scheduler cache and queue | AP with reconciliation | eventually consistent with resource-version replay | Cache lag can produce failed binds, but not committed corruption. |
| Metrics/search/analytics | AP/eventual | asynchronous ingestion and backfill | Useful for operations, not source of truth. |
| Audit and scheduling events | CP for append acceptance, replicated for durability | immutable and replayable | Used for debugging, incident review, and projection rebuilds. |

### Data Lifecycle, Backups, And Rebuilds

- Use snapshots plus WAL/event replay for the control-plane store; test restore and watch replay regularly.
- Compact old resource versions while preserving enough history for watch reconnect windows.
- Retain scheduling events, traces, and audit logs by tenant/compliance policy in object storage or warehouse.
- Rebuild scheduler caches from the CP store after scheduler restart; never trust persisted local cache as authoritative.
- Reconcile node-reported actual state against authoritative desired state and generate repair events for drift.

### Platform Building Blocks And Microservice Patterns

Use these technologies only where they fit the access pattern and correctness boundary. A strong interview answer says what is on the synchronous hot path, what is asynchronous, what is derived, and what can be rebuilt.

| Concern | Recommended Building Blocks | How To Use In This Design | Key Interview Caveat |
| --- | --- | --- | --- |
| Hot-path caching | CDN, Redis Cluster, Memcached, local in-process cache, request coalescing, stale-while-revalidate | Cache hot reads, sessions, tokens, rate-limit counters, derived cards, and expensive computed views. Invalidate through events or short TTLs. | Never make cache the only source of truth for money, permissions, scarce inventory, or irreversible state. |
| Async processing | Kafka, Pulsar, Kinesis, RabbitMQ/SQS, transactional outbox/inbox, DLQ, retry with jitter | Move notifications, indexing, analytics, projections, provider calls, and slow side effects off the user-visible path. | Consumers must be idempotent; partition by aggregate when ordering matters. |
| Stream processing | Apache Flink, Kafka Streams, Spark Structured Streaming, Beam | Build rolling counters, fraud/risk signals, ranking features, ETA/features, alerting, and near-real-time materialized views. | Use event time, watermarks, replay, and exactly-once/effectively-once sinks only where the business needs it. |
| Batch jobs and workflows | Airflow, Dagster, Argo Workflows, Temporal, Cadence, Step Functions, Spark | Run backfills, reconciliation, compaction, expiry, report generation, settlement, lifecycle management, and ML feature generation. | Keep batch workers isolated from online capacity and make every job restartable and idempotent. |
| CDC and projections | Debezium, database CDC, Kafka Connect, outbox table relay | Feed search indexes, CQRS read models, lakehouse tables, caches, and audit pipelines from committed changes. | CDC is for propagation; business commands still go through domain services. |
| Event contracts | Schema Registry, Avro, Protobuf, JSON Schema, AsyncAPI, compatibility checks | Version domain events, enforce backward/forward compatibility, and document owners and consumers. | Breaking schema changes require new event versions and migration windows. |
| CQRS and read models | Command store, query projections, materialized views, search indexes | Keep canonical writes small and strongly owned; serve read-heavy views from projections optimized for query shape. | Expose freshness/version metadata and rebuild projections from events. |
| Microservice consistency patterns | Saga/process manager, transactional outbox, inbox dedupe, idempotency keys, compensating actions | Coordinate multi-service workflows without distributed transactions. | Make every state transition explicit and auditable; avoid hidden side effects. |
| Event storming and domain modeling | Commands, aggregates, events, policies, read models, bounded contexts | Identify aggregate owners, event names, invariants, side effects, and read projections before drawing service boxes. | Services should map to ownership boundaries, not arbitrary technical layers. |
| Object storage and lakehouse | S3/GCS/Azure Blob, Iceberg, Hudi, Delta Lake, Glue/Hive catalog | Store raw events, media, attachments, audit exports, feature data, and replayable history in immutable partitions. | Keep object/lake data partitioned by date/tenant/domain key and govern retention/privacy. |
| Analytics serving | Pinot, ClickHouse, Druid, Redshift, BigQuery, Snowflake, Athena/Trino/Presto | Serve dashboards, funnels, investigations, operational analytics, ad hoc SQL, and historical reports outside OLTP. | Do not run exploratory analytics against the primary transactional database. |
| Service runtime and governance | Spring Boot, Quarkus, Micronaut, Go/gRPC, Node.js, Kubernetes, service mesh, mTLS, API gateway, OpenTelemetry, config service, feature flags | Deploy independently, enforce auth, collect traces/metrics/logs, and roll out safely with canaries and kill switches. | More services increase operational load; split only when ownership, scale, or reliability justifies it. |

For this design, use Kafka/Kinesis/Pulsar for ingestion or state-change streams, Flink/Spark for streaming computation, Airflow/Dagster/Argo/Temporal for batch or workflow orchestration, S3 + Iceberg/Hudi/Delta for lakehouse tables, and Pinot/ClickHouse/Druid for low-latency analytics.

Implementation rule: start with the simplest reliable building block, then introduce Kafka/Flink/lakehouse/OLAP/microservice patterns when scale, replay, ownership, or query shape demands them. Every added component must have a clear owner, SLO, retention policy, replay story, and failure mode.

## 8. Critical Flows

### Normal Scheduling Flow

1. User/controller creates a pod through the API server.
2. API server validates, admits, quota-checks, persists the pod as `Pending`, and emits a watch event.
3. Scheduler receives the event, enqueues the pod, and loads current node state from local cache.
4. Filter plugins remove nodes that violate hard constraints.
5. Score plugins rank feasible nodes.
6. Scheduler assumes the pod on the selected node in local cache.
7. Binder performs compare-and-set against the CP store with expected pod resource version and scheduler fencing token.
8. If bind succeeds, node agent sees assigned pod and starts it. If bind fails, scheduler rolls back assumption and requeues.

### Unschedulable Flow

1. Scheduler filters all candidate nodes and finds no feasible node.
2. It records the exact failing constraints and marks the pod unschedulable/backoff.
3. Pod is requeued when relevant cluster state changes: new node, freed resources, policy update, quota change, or backoff expiry.
4. Autoscaler may consume unschedulable signals and add capacity.

### Preemption Flow

1. High-priority pod is unschedulable.
2. Preemption engine simulates victim sets on candidate nodes.
3. It respects disruption budgets, priority, fairness, and policy.
4. If a node becomes feasible, lower-priority pods are evicted through controller-safe workflows.
5. High-priority pod is scheduled after capacity is released and state converges.

### Scheduler Failure Flow

1. Scheduler instance dies after assuming but before binding.
2. Lease expires or local assumption times out.
3. Another scheduler instance watches the same pending pod and attempts scheduling.
4. CP compare-and-set prevents duplicate binding.
5. Stuck assumed pods are found by repair jobs and requeued.

## 9. Deep-Dive Focus Areas

- **Bin packing**: balance CPU, memory, GPU, storage, and network locality without creating fragmentation that blocks future workloads.
- **Constraints**: separate hard filters from soft scoring. A node must pass all hard filters before scoring.
- **Priorities**: priority affects queue order and preemption but must not starve lower-priority tenants forever.
- **Preemption**: simulate victim sets and respect disruption budgets; preemption is expensive and should be bounded.
- **Watch consistency**: scheduler cache lag is acceptable only because binding is guarded by authoritative resource versions.
- **Failure recovery**: assumptions expire, bindings are idempotent, and controllers converge actual state.

## 10. Scaling Bottlenecks And Mitigations

| Bottleneck | Why It Happens | Mitigation |
|---|---|---|
| Full node scan per pod | Large clusters make O(pods x nodes) expensive. | Precompute node indexes, sample feasible nodes, parallelize scoring, and cache plugin results. |
| Hot rollout burst | Thousands of pods enter queue together. | Priority/fairness queues, backoff, batch scheduling, autoscaler integration. |
| Control-plane store overload | Watches, heartbeats, status updates, and binds share the same store. | Watch caches, compaction, filtered watches, rate limits, and separate metrics/audit stores. |
| Scheduler cache staleness | Watch lag or disconnect causes outdated assumptions. | Resource-version compare-and-set, watch replay, assumption rollback, and repair jobs. |
| Preemption explosion | Many victim combinations are possible. | Limit candidate nodes/victims, cache simulation, and use policy thresholds. |
| Noisy tenant | One namespace floods scheduling queue. | Namespace quotas, fairness buckets, admission throttles, and per-tenant backoff. |

## 11. Security, Privacy, Abuse Prevention, And Compliance

- Authenticate users, controllers, schedulers, node agents, and administrators separately.
- Authorize by cluster, namespace, resource type, verb, and policy.
- Use admission control for privileged pods, host mounts, host networking, image policy, and resource quotas.
- Encrypt control-plane state and object-stored traces at rest; use mTLS for internal traffic.
- Keep audit logs for pod creation, binding, policy updates, preemption, admin overrides, and secret/privileged access.
- Prevent tenant abuse through quotas, priority limits, namespace isolation, and admission throttles.
- Redact secrets, environment variables, and sensitive labels from scheduling traces and logs.

## 12. Reliability, Failure Modes, And Recovery

| Failure Mode | Impact | Recovery Strategy |
|---|---|---|
| CP store loses quorum | Unsafe writes cannot commit. | Stop binding, keep reads from last-known state only where safe, restore quorum. |
| Scheduler instance crashes | Scheduling capacity decreases. | Leaderless/replicated schedulers continue; assumed pods expire and requeue. |
| Watch stream disconnects | Cache becomes stale. | Reconnect from resource version; full relist if version compacted. |
| Node failure | Bound pods stop running. | Node controller marks node unhealthy; workload controllers recreate pods. |
| Bad scheduling policy | Poor placement or failed scheduling. | Versioned policy rollout, canary scheduler profile, rollback. |
| Event/metrics pipeline lag | Debugging and dashboards stale. | Isolate from binding path; alert on lag and replay later. |

## 13. Deployment And Operations

- Run API server, scheduler, and controllers across at least three availability zones.
- Deploy scheduler changes with canary profiles and compare scheduling decisions before global rollout.
- Keep plugin configuration versioned and audited.
- Use feature flags for new filters, scorers, and preemption policies.
- Run schema/state migrations with backward-compatible resource versions.
- Maintain runbooks for store quorum loss, watch lag, stuck pending pods, scheduler crash loops, and bad policy rollout.

## 14. Observability: SLIs, SLOs, Dashboards, Alerts

### SLIs And SLOs

| Area | SLI | Example SLO |
|---|---|---|
| Scheduling latency | time from pod pending to bound | 95% under 1s for normal pods |
| Scheduling success | bound pods / scheduling attempts | high success excluding true capacity shortage |
| Queue health | active/backoff/unschedulable queue depth | bounded by cluster and priority |
| Store health | write latency, quorum availability, compaction lag | no sustained write unavailability |
| Watch health | watch lag, reconnects, relist rate | lag within freshness target |
| Correctness | duplicate bindings, overcommit violations | zero known committed violations |

### Dashboards

- Queue depth by priority, namespace, cluster, and unschedulable reason.
- Scheduling latency by plugin profile and cluster.
- Filter rejection counts and top unschedulable constraints.
- Node utilization, fragmentation, and bin-packing efficiency.
- Store latency, watch lag, resource version compaction, and scheduler cache age.
- Preemption attempts, victims, disruption budget blocks, and rollback rate.

### Alerts

- Page on CP store quorum loss, scheduling latency SLO burn, duplicate binding, or severe queue growth.
- Ticket on rising unschedulable rate, plugin latency regression, watch lag, or fragmentation trends.
- Route policy/regression alerts to scheduler owners with recent deployment and policy versions.

## 15. Cost Model And Trade-Offs

### Cost Drivers

- Control-plane store replicas and write amplification.
- Scheduler CPU for filter/score/preemption.
- Watch fanout and network traffic.
- Metrics, traces, scheduling event retention, and audit logs.
- Idle headroom needed to preserve scheduling latency during bursts.

### Cost Controls

- Keep CP store values compact and move large specs/traces to object storage.
- Use filtered watches and compaction.
- Sample expensive scheduling traces while retaining all failures and audits.
- Precompute node indexes to reduce CPU per scheduling attempt.
- Tier old events and metrics to cheaper storage.

## 16. Key Trade-Offs

| Decision | Option A | Option B | Interview Guidance |
|---|---|---|---|
| Binding consistency | CP compare-and-set | AP/local bind | Use CP; duplicate placement or overcommit is worse than temporary scheduling unavailability. |
| Scheduling cache | Rebuilt local cache | Query CP store every time | Local cache is required for scale; protect correctness with resource-version bind. |
| Bin packing | Max utilization | Spread for resilience | Choose based on workload class; expose policy profiles. |
| Preemption | Aggressive | Conservative | Aggressive improves high-priority latency but hurts stability. |
| Cluster scale | One huge cluster | Many cells/clusters | Cells reduce blast radius and control-plane hot spots. |

## 17. Common Interview Follow-Ups

- How do you avoid scanning every node for every pod?
- What prevents two scheduler instances from binding the same pod?
- How does the scheduler recover after a watch disconnect?
- How do you handle high-priority pods when the cluster is full?
- Which data is strongly consistent and which data is only eventually consistent?
- How do you debug why a pod was not scheduled?
- How does the design change for 100K nodes?

## 18. Final Interview Checklist

- Clarify scheduler versus node-agent responsibilities.
- State the authoritative store and resource-version compare-and-set binding.
- Separate hard filters from scoring plugins.
- Explain queueing, backoff, fairness, priority, and preemption.
- Cover watch-based cache reconstruction and failure recovery.
- Include database choice, replication, sharding, indexing, partitioning, CAP, and eventual consistency.
- Cover security, observability, deployment, and cost.

## 19. World-Class Interview Review

### What A Strong Interview Answer Must Demonstrate

- **Correctness boundary:** binding is committed only through the CP state store with expected resource version and fencing.
- **Hot path clarity:** explain pending queue -> filter -> score -> assume -> bind -> node execution.
- **Service ownership:** API server owns validation/persistence; scheduler owns placement decision; node agent owns execution.
- **Data ownership:** cluster state store is canonical; scheduler cache, metrics, search, and analytics are derived.
- **Failure recovery:** watch replay, assumption expiry, resource-version conflicts, and controller reconciliation prevent corruption.
- **Operational maturity:** include scheduling traces, unschedulable reasons, plugin latency, queue depth, and policy rollback.

### Bar-Raiser Drill-Down Prompts

- What exact compare-and-set prevents duplicate binding?
- How do you keep scheduler cache consistent enough without making every decision query the store?
- How do you shard a 100K-node cluster?
- How do you support custom scheduling plugins without making the scheduler unsafe?
- What metric pages the on-call before workloads stop being scheduled?

### Common Weak Answers To Avoid

- Treating the scheduler as the component that runs containers.
- Ignoring resource versions and duplicate binding races.
- Scanning all nodes synchronously for every pod at massive scale.
- Using Redis or local memory as authoritative binding state.
- Saying "eventual consistency" without explaining how bind correctness is still protected.

### Domain-Specific Bar Raiser Notes

- Use CP semantics for control-plane state and AP/eventual semantics only for caches, metrics, and derived views.
- Separate scheduling policy from scheduling execution so policy can be versioned, canaried, and rolled back.
- Explain preemption carefully; it is a correctness and stability risk, not only an optimization.

### 5-Minute Whiteboard Structure

- First minute: scope scheduler responsibility and main objects: pod, node, binding, policy, lease.
- Minutes 2-3: draw API server, CP store, watch cache, scheduler queue, filter/score/preemption, binder, node agents.
- Minute 4: walk normal scheduling and scheduler-crash recovery.
- Minute 5: close with database choices, CAP consistency, scaling bottlenecks, observability, and trade-offs.
