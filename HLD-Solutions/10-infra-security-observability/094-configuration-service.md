# Configuration Service

## 1. Requirements

### Functional Requirements
- **Hierarchical Key-Value Storage**: Nested namespaces (global/env/service/instance)
- **Namespaces**: Logical grouping of configuration by service/team/environment
- **Versioning**: Every change creates a new version, full history retained
- **Change Notifications (Watch)**: Real-time push when config values change
- **Access Control**: Per-namespace/key RBAC with encrypted secrets
- **Encryption**: Transparent encryption for sensitive values (passwords, keys)
- **Inheritance/Override**: Global → Environment → Service → Instance cascade
- **Validation Schemas**: JSON Schema validation before accepting config changes
- **Rollback**: Instant rollback to any previous version
- **Audit Log**: Who changed what, when, with diff

### Non-Functional Requirements
- **Availability**: 99.999% (config is on critical path for every service)
- **Latency**: <5ms for reads (local cache), <50ms for writes
- **Consistency**: Linearizable reads for critical config, bounded staleness for others
- **Scale**: 1M keys, 100K services watching, 10K writes/second
- **Durability**: Zero data loss (Raft consensus for writes)
- **Partition Tolerance**: Reads available even during network partitions (stale OK)

## 2. Capacity Estimation

### Traffic
- Read QPS: 1M (mostly served from local SDK cache)
- Network reads (cache miss): 100K QPS
- Write QPS: 10K (config changes, deployments)
- Watch connections: 100K concurrent gRPC streams
- Watch notifications: 50K/second (during deployments)

### Storage
- Config keys: 1M × 2KB avg value = 2GB active
- Version history: 100 versions/key avg × 1M × 500B delta = 50GB
- Audit log: 10K writes/s × 500 bytes = 432GB/day (tiered to cold storage)

### Compute
- Raft leader writes: 10K/s × 1ms = 10 cores (leader node)
- Watch notification fan-out: 50K notifications × 100 watchers = 5M messages/s
- Schema validation: 10K/s × 0.5ms = 5 cores

## 3. Data Modeling

### Database Schemas

```sql
-- Configuration Namespaces
CREATE TABLE config_namespaces (
    namespace_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    path                VARCHAR(500) NOT NULL UNIQUE,  -- e.g., "prod/us-east/payment-service"
    parent_path         VARCHAR(500),                  -- Parent for inheritance
    description         TEXT,
    owner_team          VARCHAR(100),
    schema_id           UUID,                          -- Validation schema
    encryption_enabled  BOOLEAN DEFAULT false,
    encryption_key_id   VARCHAR(100),
    retention_policy    JSONB DEFAULT '{"versions_to_keep": 100}',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ns_path ON config_namespaces(path);
CREATE INDEX idx_ns_parent ON config_namespaces(parent_path);
CREATE INDEX idx_ns_owner ON config_namespaces(owner_team);

-- Configuration Keys (current state)
CREATE TABLE config_entries (
    entry_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    namespace_id        UUID NOT NULL REFERENCES config_namespaces(namespace_id),
    key                 VARCHAR(500) NOT NULL,
    value               BYTEA NOT NULL,              -- Encrypted if sensitive
    value_type          VARCHAR(20) NOT NULL DEFAULT 'STRING',  -- STRING, JSON, INT, BOOL, SECRET
    is_encrypted        BOOLEAN DEFAULT false,
    version             BIGINT NOT NULL DEFAULT 1,
    schema_validation   JSONB,                       -- Per-key JSON Schema
    metadata            JSONB DEFAULT '{}',
    ttl_seconds         INT,                         -- Optional expiry
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_by          VARCHAR(100) NOT NULL,
    UNIQUE(namespace_id, key)
);

CREATE INDEX idx_entries_ns_key ON config_entries(namespace_id, key);
CREATE INDEX idx_entries_version ON config_entries(namespace_id, version);
CREATE INDEX idx_entries_updated ON config_entries(updated_at);

-- Version History
CREATE TABLE config_versions (
    version_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_id            UUID NOT NULL REFERENCES config_entries(entry_id),
    namespace_id        UUID NOT NULL,
    key                 VARCHAR(500) NOT NULL,
    value               BYTEA NOT NULL,
    version             BIGINT NOT NULL,
    change_type         VARCHAR(10) NOT NULL,        -- SET, DELETE, ROLLBACK
    changed_by          VARCHAR(100) NOT NULL,
    change_source       VARCHAR(50),                 -- API, GITOPS, EMERGENCY
    change_comment      TEXT,
    previous_version_id UUID,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_versions_entry ON config_versions(entry_id, version DESC);
CREATE INDEX idx_versions_ns ON config_versions(namespace_id, created_at DESC);
CREATE INDEX idx_versions_by ON config_versions(changed_by, created_at DESC);

-- Watch Subscriptions (persistent)
CREATE TABLE config_watches (
    watch_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           VARCHAR(200) NOT NULL,
    namespace_id        UUID NOT NULL,
    key_pattern         VARCHAR(500) NOT NULL,       -- Glob pattern (* for all)
    last_seen_version   BIGINT DEFAULT 0,
    notification_url    VARCHAR(500),                -- Webhook (optional)
    is_active           BOOLEAN DEFAULT true,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    last_notified_at    TIMESTAMPTZ
);

CREATE INDEX idx_watches_ns ON config_watches(namespace_id, is_active);
CREATE INDEX idx_watches_client ON config_watches(client_id);

-- Access Control
CREATE TABLE config_acl (
    acl_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    namespace_pattern   VARCHAR(500) NOT NULL,       -- Path pattern with wildcards
    principal_type      VARCHAR(20) NOT NULL,        -- USER, SERVICE, TEAM
    principal_id        VARCHAR(200) NOT NULL,
    permissions         TEXT[] NOT NULL,             -- READ, WRITE, ADMIN, WATCH
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_acl_ns ON config_acl(namespace_pattern);
CREATE INDEX idx_acl_principal ON config_acl(principal_type, principal_id);

-- Audit Log
CREATE TABLE config_audit_log (
    audit_id            UUID DEFAULT gen_random_uuid(),
    event_time          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    namespace_path      VARCHAR(500) NOT NULL,
    key                 VARCHAR(500),
    action              VARCHAR(20) NOT NULL,        -- READ, SET, DELETE, ROLLBACK, WATCH
    actor               VARCHAR(200) NOT NULL,
    actor_type          VARCHAR(20) NOT NULL,        -- USER, SERVICE, SYSTEM
    old_value_hash      VARCHAR(64),                 -- SHA-256 (don't store secrets in audit)
    new_value_hash      VARCHAR(64),
    source_ip           INET,
    change_source       VARCHAR(50),
    metadata            JSONB DEFAULT '{}'
) PARTITION BY RANGE (event_time);

CREATE INDEX idx_audit_ns ON config_audit_log(namespace_path, event_time DESC);
CREATE INDEX idx_audit_actor ON config_audit_log(actor, event_time DESC);

-- Validation Schemas
CREATE TABLE config_schemas (
    schema_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                VARCHAR(255) NOT NULL,
    json_schema         JSONB NOT NULL,             -- JSON Schema definition
    version             INT DEFAULT 1,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

### Kafka Topics

```yaml
topics:
  config-changes:
    partitions: 32
    replication-factor: 3
    retention.ms: 604800000       # 7 days
    cleanup.policy: compact       # Keep latest per key

  config-notifications:
    partitions: 64
    replication-factor: 3
    retention.ms: 3600000         # 1 hour
    max.message.bytes: 262144

  config-audit:
    partitions: 16
    replication-factor: 3
    retention.ms: 2592000000     # 30 days
```

### Redis Configuration

```yaml
redis:
  config-cache:
    cluster: true
    nodes: 6
    maxmemory: 8gb
    maxmemory-policy: noeviction
    data-structures:
      - hash: "config:{namespace}:{key}"          # Current value + metadata
      - string: "config:version:{namespace}"      # Namespace version counter
      - sorted-set: "config:changes:{namespace}"  # Recent changes for watch
      - pubsub: "config:notify:{namespace}"       # Real-time notifications
      - hash: "config:resolved:{service}:{env}"   # Fully resolved config (with inheritance)

  watch-state:
    cluster: true
    nodes: 3
    maxmemory: 4gb
    maxmemory-policy: volatile-lru
    data-structures:
      - hash: "watch:client:{client_id}"          # Client watch state
      - set: "watch:ns:{namespace}"               # Clients watching namespace
```

## 4. High-Level Design

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                          CONFIGURATION SERVICE                                     │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                    │
│  Config Consumers:                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐     │
│  │ Service SDK  │  │  CLI Tool    │  │  Web UI      │  │  GitOps Agent    │     │
│  │ (embedded)   │  │  (admin)     │  │  (dashboard) │  │  (reconciler)    │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘     │
│         │                  │                  │                    │               │
│         └──────────────────┴──────────────────┴────────────────────┘               │
│                                    │                                               │
│                                    ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                        API Gateway / Load Balancer                            │  │
│  └───────────────────────────────────┬─────────────────────────────────────────┘  │
│                                      │                                             │
│         ┌────────────────────────────┼────────────────────────────┐               │
│         ▼                            ▼                            ▼               │
│  ┌───────────────┐      ┌────────────────────┐      ┌───────────────────┐        │
│  │ Read Path     │      │  Write Path        │      │  Watch Path       │        │
│  │               │      │                    │      │                   │        │
│  │ • Local cache │      │ • Raft consensus   │      │ • gRPC streaming │        │
│  │ • Redis       │      │ • Schema validate  │      │ • Long-poll HTTP │        │
│  │ • Stale reads │      │ • Encrypt secrets  │      │ • SSE fallback   │        │
│  │   acceptable  │      │ • Version bump     │      │ • Webhook push   │        │
│  └───────┬───────┘      └─────────┬──────────┘      └─────────┬─────────┘        │
│          │                         │                            │                   │
│          └─────────────────────────┼────────────────────────────┘                   │
│                                    ▼                                                │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                     Raft Consensus Group (3 or 5 nodes)                       │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                      │  │
│  │  │   Leader     │  │  Follower 1  │  │  Follower 2  │                      │  │
│  │  │  (writes)    │  │  (reads OK)  │  │  (reads OK)  │                      │  │
│  │  │              │  │              │  │              │                        │  │
│  │  │  WAL + State │  │  WAL + State │  │  WAL + State │                      │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                      │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                               │
│                                    ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                        Storage Layer                                          │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │  │
│  │  │ PostgreSQL   │  │  Redis Cache │  │  KMS/Vault   │  │  S3 (Audit   │  │  │
│  │  │ (persistent) │  │  (hot path)  │  │  (secrets)   │  │   cold store)│  │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └───────────────┘  │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                    │
│  Inheritance Resolution:                                                          │
│  global/database.pool_size=10                                                     │
│    └─► prod/database.pool_size=50           (env override)                        │
│         └─► prod/payment-svc/database.pool_size=100  (service override)           │
│              └─► prod/payment-svc/i-abc123/database.pool_size=200 (instance)      │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## 5. Low-Level Design (APIs)

### gRPC + REST APIs

```yaml
# Set Configuration Value
PUT /api/v1/config/{namespace}/{key}
Request:
  {
    "value": "postgresql://db.internal:5432/payments",
    "value_type": "STRING",
    "is_secret": true,
    "comment": "Updated DB connection for new cluster",
    "schema": {
      "type": "string",
      "pattern": "^postgresql://.*"
    }
  }
Response: 200
  {
    "namespace": "prod/us-east/payment-service",
    "key": "database.connection_string",
    "version": 42,
    "previous_version": 41,
    "encrypted": true,
    "updated_at": "2024-01-15T10:30:00Z",
    "updated_by": "deploy-bot@ci"
  }

# Get Configuration (with inheritance resolution)
GET /api/v1/config/{namespace}/{key}?resolve=true&consistency=linearizable
Response: 200
  {
    "namespace": "prod/us-east/payment-service",
    "key": "database.pool_size",
    "value": "100",
    "value_type": "INT",
    "version": 15,
    "resolved_from": "prod/us-east/payment-service",  # Where the value came from
    "inheritance_chain": [
      { "namespace": "global", "value": "10", "version": 3 },
      { "namespace": "prod", "value": "50", "version": 8 },
      { "namespace": "prod/us-east/payment-service", "value": "100", "version": 15 }
    ],
    "metadata": {
      "last_changed_by": "platform-team@ci",
      "last_changed_at": "2024-01-10T08:00:00Z"
    }
  }

# Get All Config for Service (bulk, for SDK initialization)
GET /api/v1/config/{namespace}?recursive=true&resolve=true
Response: 200
  {
    "namespace": "prod/us-east/payment-service",
    "version": 142,
    "entries": {
      "database.connection_string": { "value": "[ENCRYPTED]", "type": "SECRET", "version": 42 },
      "database.pool_size": { "value": "100", "type": "INT", "version": 15 },
      "cache.ttl_seconds": { "value": "300", "type": "INT", "version": 7 },
      "feature.retry_enabled": { "value": "true", "type": "BOOL", "version": 3 }
    }
  }

# Watch for Changes (gRPC streaming)
# gRPC: rpc Watch(WatchRequest) returns (stream WatchEvent)
POST /api/v1/config/{namespace}/watch
Request:
  {
    "key_patterns": ["database.*", "cache.*"],
    "since_version": 140,
    "delivery": "stream"  # or "long-poll" or "webhook"
  }
Response: 200 (streaming)
  # Event 1:
  {
    "event_type": "UPDATED",
    "namespace": "prod/us-east/payment-service",
    "key": "database.pool_size",
    "new_value": "150",
    "old_value": "100",
    "version": 143,
    "changed_by": "auto-scaler",
    "timestamp": "2024-01-15T14:30:00Z"
  }

# Rollback
POST /api/v1/config/{namespace}/{key}/rollback
Request:
  {
    "target_version": 38,
    "reason": "Reverting broken connection string",
    "emergency": true
  }
Response: 200
  {
    "key": "database.connection_string",
    "rolled_back_from_version": 42,
    "rolled_back_to_version": 38,
    "new_version": 43,  # Rollback creates a new version
    "restored_value_hash": "sha256:abc123..."
  }

# Batch Set (atomic multi-key update)
POST /api/v1/config/{namespace}/batch
Request:
  {
    "operations": [
      { "op": "SET", "key": "database.host", "value": "new-db.internal" },
      { "op": "SET", "key": "database.port", "value": "5433" },
      { "op": "DELETE", "key": "database.old_host" }
    ],
    "atomic": true,
    "comment": "Database migration cutover"
  }
Response: 200
  {
    "results": [...],
    "new_namespace_version": 145,
    "applied_at": "2024-01-15T15:00:00Z"
  }
```

## 6. Deep Dive: Watch Mechanism

### Efficient Change Detection

```python
import asyncio
from typing import Dict, Set, List
import grpc

class WatchManager:
    """
    Manages watch subscriptions and delivers config change notifications.
    Supports multiple delivery mechanisms:
    - gRPC server streaming (preferred for services)
    - Long-polling HTTP (for environments without gRPC)
    - SSE (for web dashboards)
    - Webhook push (for external systems)
    """
    
    def __init__(self, redis, raft_log):
        self.redis = redis
        self.raft_log = raft_log
        self.active_watches: Dict[str, Set[WatchStream]] = {}  # namespace → streams
        self.version_vectors: Dict[str, int] = {}  # namespace → last known version
    
    async def register_watch(self, client_id: str, namespace: str, 
                            key_patterns: List[str], since_version: int) -> WatchStream:
        """Register a new watch subscription."""
        stream = WatchStream(
            client_id=client_id,
            namespace=namespace,
            key_patterns=key_patterns,
            last_seen_version=since_version
        )
        
        # Add to active watches
        if namespace not in self.active_watches:
            self.active_watches[namespace] = set()
        self.active_watches[namespace].add(stream)
        
        # Send any missed events since since_version
        missed = await self._get_changes_since(namespace, since_version)
        for change in missed:
            if stream.matches(change.key):
                await stream.send(change)
        
        return stream
    
    async def notify_change(self, change: ConfigChange):
        """
        Called by write path after successful Raft commit.
        Fans out notification to all watching clients.
        """
        namespace = change.namespace
        
        # 1. Publish to Redis pub/sub for multi-node fan-out
        await self.redis.publish(
            f"config:notify:{namespace}",
            json.dumps(change.to_dict())
        )
        
        # 2. Store in sorted set for catch-up (missed events recovery)
        await self.redis.zadd(
            f"config:changes:{namespace}",
            {json.dumps(change.to_dict()): change.version}
        )
        # Trim to keep only last 1000 changes
        await self.redis.zremrangebyrank(f"config:changes:{namespace}", 0, -1001)
        
        # 3. Local fan-out to connected streams
        streams = self.active_watches.get(namespace, set())
        dead_streams = set()
        
        for stream in streams:
            if stream.matches(change.key):
                try:
                    await stream.send(change)
                except StreamClosed:
                    dead_streams.add(stream)
        
        # Cleanup
        self.active_watches[namespace] -= dead_streams
    
    async def _get_changes_since(self, namespace: str, version: int) -> List[ConfigChange]:
        """Get all changes since a specific version for catch-up."""
        raw = await self.redis.zrangebyscore(
            f"config:changes:{namespace}",
            min=version + 1,
            max='+inf'
        )
        return [ConfigChange.from_dict(json.loads(r)) for r in raw]


class LongPollHandler:
    """
    HTTP long-polling fallback for watch.
    Client sends request with current version, server holds until change or timeout.
    """
    
    LONG_POLL_TIMEOUT = 30  # seconds
    
    async def handle(self, request) -> Response:
        namespace = request.path_params['namespace']
        since_version = int(request.query_params.get('since_version', 0))
        timeout = min(int(request.query_params.get('timeout', 30)), self.LONG_POLL_TIMEOUT)
        
        # Check if there are already new changes
        current_version = await self.redis.get(f"config:version:{namespace}")
        if current_version and int(current_version) > since_version:
            changes = await self._get_changes_since(namespace, since_version)
            return Response(200, json={'changes': [c.to_dict() for c in changes]})
        
        # Wait for change or timeout
        event = asyncio.Event()
        
        async def on_change(change):
            event.set()
        
        # Subscribe to changes
        watcher = await self.watch_manager.register_callback(namespace, on_change)
        
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            # Change occurred
            changes = await self._get_changes_since(namespace, since_version)
            return Response(200, json={'changes': [c.to_dict() for c in changes]})
        except asyncio.TimeoutError:
            # No changes within timeout
            return Response(200, json={'changes': [], 'version': since_version})
        finally:
            await watcher.unsubscribe()


class BurstBatcher:
    """
    Batches rapid-fire config changes into single notification.
    During deployments, many keys change simultaneously.
    Instead of N notifications, send 1 batch notification.
    """
    
    BATCH_WINDOW_MS = 100  # Collect changes for 100ms before notifying
    
    def __init__(self, watch_manager: WatchManager):
        self.watch_manager = watch_manager
        self.pending: Dict[str, List[ConfigChange]] = {}  # namespace → changes
        self.timers: Dict[str, asyncio.Task] = {}
    
    async def queue_notification(self, change: ConfigChange):
        """Queue a change for batched notification."""
        namespace = change.namespace
        
        if namespace not in self.pending:
            self.pending[namespace] = []
        self.pending[namespace].append(change)
        
        # Reset/start batch timer
        if namespace in self.timers:
            self.timers[namespace].cancel()
        
        self.timers[namespace] = asyncio.create_task(
            self._flush_after_delay(namespace)
        )
    
    async def _flush_after_delay(self, namespace: str):
        """Wait for batch window, then flush all pending changes."""
        await asyncio.sleep(self.BATCH_WINDOW_MS / 1000)
        
        changes = self.pending.pop(namespace, [])
        del self.timers[namespace]
        
        if changes:
            # Send as batch notification
            batch = BatchNotification(
                namespace=namespace,
                changes=changes,
                version=max(c.version for c in changes)
            )
            await self.watch_manager.notify_batch(batch)
```

## 7. Deep Dive: Consistency Model

### Raft-Based Consensus for Writes

```python
class RaftConfigStore:
    """
    Raft consensus for linearizable writes.
    Reads can be served from followers with bounded staleness.
    """
    
    def __init__(self, node_id: str, peers: List[str]):
        self.node_id = node_id
        self.peers = peers
        self.state = {}  # In-memory state machine
        self.wal = WriteAheadLog(f"/data/raft/{node_id}")
        self.current_term = 0
        self.voted_for = None
        self.commit_index = 0
        self.role = 'FOLLOWER'
    
    async def write(self, namespace: str, key: str, value: bytes, 
                    metadata: dict) -> WriteResult:
        """
        Write a config value through Raft consensus.
        Only leader can accept writes.
        """
        if self.role != 'LEADER':
            leader = self._get_current_leader()
            raise NotLeaderError(leader_address=leader)
        
        # 1. Validate schema (before proposing to Raft)
        await self._validate_schema(namespace, key, value)
        
        # 2. Create log entry
        entry = LogEntry(
            term=self.current_term,
            index=self.wal.next_index(),
            command=SetCommand(namespace=namespace, key=key, value=value, metadata=metadata)
        )
        
        # 3. Append to local WAL
        await self.wal.append(entry)
        
        # 4. Replicate to followers (wait for majority)
        ack_count = 1  # Leader counts as 1
        required = (len(self.peers) + 1) // 2 + 1
        
        replication_tasks = [
            self._replicate_to_peer(peer, entry) for peer in self.peers
        ]
        
        for coro in asyncio.as_completed(replication_tasks):
            try:
                await coro
                ack_count += 1
                if ack_count >= required:
                    break
            except ReplicationError:
                continue
        
        if ack_count < required:
            raise ConsensusFailedError("Failed to reach majority")
        
        # 5. Commit (apply to state machine)
        self.commit_index = entry.index
        result = await self._apply_to_state_machine(entry)
        
        # 6. Notify watchers
        await self.watch_manager.notify_change(ConfigChange(
            namespace=namespace,
            key=key,
            new_value=value,
            version=result.version,
            changed_by=metadata.get('actor')
        ))
        
        return result
    
    async def read(self, namespace: str, key: str, 
                   consistency: str = 'linearizable') -> ReadResult:
        """
        Read with configurable consistency level.
        - linearizable: Must read from leader (or verify leadership)
        - serializable: Can read from any node (may be stale)
        - bounded_staleness: Read from follower if within staleness bound
        """
        if consistency == 'linearizable':
            # Verify we're still leader (or forward to leader)
            if self.role == 'LEADER':
                await self._verify_leadership()  # Send heartbeat, ensure no new leader
            else:
                return await self._forward_to_leader('read', namespace, key)
            
            return self._read_from_state(namespace, key)
        
        elif consistency == 'bounded_staleness':
            # Check if local state is within staleness bound
            staleness = self._compute_staleness()
            if staleness.seconds < 5:  # 5-second staleness bound
                return self._read_from_state(namespace, key)
            else:
                # Too stale, read from leader
                return await self._forward_to_leader('read', namespace, key)
        
        else:  # serializable (local read, may be stale)
            return self._read_from_state(namespace, key)


class InheritanceResolver:
    """
    Resolves configuration values through the inheritance hierarchy.
    More specific namespaces override less specific ones.
    """
    
    HIERARCHY = ['global', 'environment', 'region', 'service', 'instance']
    
    async def resolve(self, namespace: str, key: str) -> ResolvedValue:
        """
        Resolve a key by walking up the namespace hierarchy.
        Example: prod/us-east/payment-svc/i-abc123
        Checks: instance → service → region → environment → global
        """
        parts = namespace.split('/')
        
        # Build hierarchy paths (most specific to least)
        paths = []
        for i in range(len(parts), 0, -1):
            paths.append('/'.join(parts[:i]))
        paths.append('global')
        
        # Check each level
        chain = []
        resolved_value = None
        resolved_from = None
        
        for path in reversed(paths):  # Start from global (least specific)
            entry = await self.store.get(path, key)
            if entry:
                chain.append(ResolutionStep(namespace=path, value=entry.value, version=entry.version))
                resolved_value = entry.value
                resolved_from = path
        
        if resolved_value is None:
            raise KeyNotFoundError(f"Key '{key}' not found in hierarchy for '{namespace}'")
        
        return ResolvedValue(
            value=resolved_value,
            resolved_from=resolved_from,
            inheritance_chain=chain
        )
```

## 8. Deep Dive: Deployment Patterns

### GitOps Configuration Management

```python
class GitOpsReconciler:
    """
    Reconciles configuration from Git repository.
    Git is the source of truth; config service reflects Git state.
    """
    
    async def reconcile(self, repo_path: str, branch: str = 'main'):
        """
        Compare Git state with config service state.
        Apply diffs as atomic batch updates.
        """
        # 1. Fetch latest from Git
        git_configs = await self._parse_git_configs(repo_path, branch)
        
        # 2. Get current state from config service
        current_configs = await self.config_client.get_all_namespaces()
        
        # 3. Compute diff
        changes = self._compute_diff(git_configs, current_configs)
        
        if not changes:
            return ReconcileResult(status='IN_SYNC')
        
        # 4. Apply changes (with validation)
        for namespace, ops in changes.items():
            await self.config_client.batch_set(
                namespace=namespace,
                operations=ops,
                source='GITOPS',
                comment=f"Reconciled from git commit {self._get_head_sha(repo_path)}"
            )
        
        return ReconcileResult(status='APPLIED', changes_count=sum(len(v) for v in changes.values()))


class CanaryConfigRollout:
    """
    Gradual config rollout: apply to canary instances first,
    monitor, then promote to full fleet.
    """
    
    async def rollout(self, namespace: str, key: str, new_value: str,
                     canary_percent: int = 10, monitor_duration_s: int = 300):
        """
        1. Apply to canary instances
        2. Monitor for errors
        3. Promote or rollback
        """
        # 1. Set at canary level
        canary_ns = f"{namespace}/canary"
        await self.config_client.set(canary_ns, key, new_value,
                                     comment=f"Canary rollout: {canary_percent}%")
        
        # 2. Monitor
        start = time.time()
        while time.time() - start < monitor_duration_s:
            metrics = await self.monitoring.get_error_rate(
                service=self._extract_service(namespace),
                filter={'config_version': 'canary'}
            )
            
            if metrics.error_rate > self.threshold:
                # Rollback canary
                await self.config_client.delete(canary_ns, key)
                return RolloutResult(status='ROLLED_BACK', reason='Error rate exceeded threshold')
            
            await asyncio.sleep(30)
        
        # 3. Promote: set at main namespace level
        await self.config_client.set(namespace, key, new_value,
                                     comment=f"Promoted from canary after {monitor_duration_s}s")
        await self.config_client.delete(canary_ns, key)
        
        return RolloutResult(status='PROMOTED')


class EmergencyOverride:
    """
    Break-glass procedure for emergency config changes.
    Bypasses normal approval flow but creates high-visibility audit entry.
    """
    
    async def emergency_set(self, namespace: str, key: str, value: str,
                           actor: str, justification: str) -> dict:
        """Apply emergency override with enhanced audit trail."""
        # 1. Verify actor has break-glass permission
        if not await self.acl.has_permission(actor, namespace, 'EMERGENCY_WRITE'):
            raise PermissionDenied("Actor lacks EMERGENCY_WRITE permission")
        
        # 2. Apply immediately (bypass schema validation if needed)
        result = await self.config_client.set(
            namespace, key, value,
            metadata={
                'source': 'EMERGENCY',
                'actor': actor,
                'justification': justification,
                'bypass_validation': True
            }
        )
        
        # 3. Alert on-call and audit
        await self.alerting.send_emergency_alert(
            f"EMERGENCY CONFIG CHANGE by {actor}: {namespace}/{key}",
            details=justification
        )
        
        # 4. Create follow-up ticket
        await self.ticketing.create(
            title=f"Follow-up: Emergency config change {namespace}/{key}",
            assignee=actor,
            body=f"Justification: {justification}\nPlease create PR to codify this change."
        )
        
        return result
```

## 9. Component Optimization

### SDK with Local Cache

```python
class ConfigSDK:
    """
    Embedded SDK for services to consume configuration.
    Features: local cache, watch, inheritance resolution, hot-reload.
    """
    
    def __init__(self, namespace: str, server_address: str):
        self.namespace = namespace
        self.server = server_address
        self.cache: Dict[str, ConfigValue] = {}
        self.version = 0
        self.callbacks: Dict[str, List[Callable]] = {}  # key → callbacks
        self._watch_task = None
    
    async def initialize(self):
        """Load all config and start watching for changes."""
        # 1. Load from persistent cache (disk) for fast startup
        self.cache = await self._load_disk_cache()
        
        # 2. Fetch latest from server
        try:
            response = await self._fetch_all()
            self.cache = response.entries
            self.version = response.version
            await self._save_disk_cache()
        except ConnectionError:
            # Use disk cache if server unavailable at startup
            pass
        
        # 3. Start watch stream
        self._watch_task = asyncio.create_task(self._watch_loop())
    
    def get(self, key: str, default=None) -> Any:
        """Get config value (from local cache, <0.01ms)."""
        entry = self.cache.get(key)
        if entry is None:
            return default
        return entry.value
    
    def get_int(self, key: str, default: int = 0) -> int:
        return int(self.get(key, default))
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        val = self.get(key, str(default))
        return val.lower() in ('true', '1', 'yes')
    
    def on_change(self, key: str, callback: Callable):
        """Register callback for when a specific key changes."""
        if key not in self.callbacks:
            self.callbacks[key] = []
        self.callbacks[key].append(callback)
    
    async def _watch_loop(self):
        """Maintain persistent watch connection with reconnect."""
        while True:
            try:
                async for event in self._stream_watch():
                    self._apply_change(event)
            except Exception as e:
                await asyncio.sleep(min(2 ** self._retry_count, 30))
                self._retry_count += 1
    
    def _apply_change(self, event: WatchEvent):
        """Apply a change from watch stream to local cache."""
        old_value = self.cache.get(event.key)
        
        if event.event_type == 'UPDATED':
            self.cache[event.key] = ConfigValue(value=event.new_value, version=event.version)
        elif event.event_type == 'DELETED':
            self.cache.pop(event.key, None)
        
        self.version = event.version
        
        # Fire callbacks
        for callback in self.callbacks.get(event.key, []):
            try:
                callback(event.key, event.new_value, old_value)
            except Exception:
                pass  # Don't let callback errors break the SDK
```

## 10. Observability

### Metrics

```yaml
metrics:
  - config.reads.total:              Counter (tags: namespace, consistency_level)
  - config.reads.latency_ms:         Histogram (tags: source)  # cache, redis, raft
  - config.writes.total:             Counter (tags: namespace, source)
  - config.writes.latency_ms:        Histogram
  - config.writes.validation_failures: Counter (tags: namespace, schema)
  - config.watch.active_streams:     Gauge (tags: namespace)
  - config.watch.notifications_sent: Counter (tags: namespace)
  - config.watch.lag_ms:             Histogram (time from write to notification)
  - config.raft.leader_elections:    Counter
  - config.raft.replication_lag:     Gauge (tags: follower_id)
  - config.raft.commit_latency_ms:   Histogram
  - config.cache.hit_rate:           Gauge (tags: layer)  # sdk, redis
  - config.inheritance.resolution_ms: Histogram (tags: depth)
  - config.rollbacks.total:          Counter (tags: namespace, reason)
  - config.emergency.overrides:      Counter

alerts:
  - name: RaftLeaderLost
    condition: config.raft.leader_elections increase > 3 in 1m
    severity: critical
  - name: WatchLagHigh
    condition: p99(config.watch.lag_ms) > 5000
    severity: warning
  - name: WriteLatencyHigh
    condition: p99(config.writes.latency_ms) > 100
    severity: warning
  - name: EmergencyOverride
    condition: config.emergency.overrides > 0
    severity: critical
```

## 11. Considerations

### Trade-offs
| Decision | Chosen | Alternative | Rationale |
|----------|--------|-------------|-----------|
| Consensus | Raft (custom) | etcd/Consul (use existing) | Full control over read consistency trade-offs, custom inheritance |
| Watch delivery | gRPC streaming | Polling / WebSocket | Bi-directional not needed, gRPC streaming = efficient, typed |
| Secret encryption | Envelope encryption (KMS) | Vault transit | Lower latency (local decrypt), KMS for key management only |
| Inheritance | Namespace path hierarchy | Explicit config includes | Intuitive, mirrors deployment topology |
| Batch changes | Atomic multi-key | Individual writes | Deployments change multiple keys atomically |

### Consistency vs Availability
- **Writes**: Always linearizable (Raft majority required). Unavailable if no majority.
- **Reads (critical)**: Linearizable from leader. Use for secrets rotation, feature kills.
- **Reads (normal)**: Bounded staleness from any node. Acceptable for most config reads.
- **Partition behavior**: Minority partition can still serve stale reads (SDK cache), cannot write.

### Failure Handling
- Raft leader failure: Automatic election in <5s, writes blocked during election
- Network partition: Majority partition continues, minority serves stale reads
- SDK server disconnect: Continue with cached values, exponential backoff reconnect
- Encryption key unavailable: Fail reads for encrypted values, serve non-encrypted normally
- Schema validation failure: Reject write, return detailed validation errors

### Operational Patterns
- **Config-as-Code**: Git repo as source of truth, reconciler syncs to service
- **Canary rollout**: Apply to subset first, monitor, then promote
- **Emergency override**: Break-glass with enhanced audit + auto-ticket
- **Rollback**: Instant (new version pointing to old value), no destructive operation
