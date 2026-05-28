# Design Google Docs Collaborative Editing - World-Class System Design

## 1. Functional Requirements

| # | Requirement | Description |
|---|---|---|
| FR1 | Real-time collaboration | Multiple users edit the same document simultaneously with <100ms visible latency |
| FR2 | Conflict resolution | Automatically resolve concurrent edits without data loss (OT/CRDT) |
| FR3 | Cursor/selection sharing | Show each collaborator's cursor position and text selection in real-time |
| FR4 | Version history | Complete revision history with ability to restore any previous version |
| FR5 | Rich text editing | Bold, italic, headings, lists, tables, images, links, comments |
| FR6 | Comments & suggestions | Inline comments, threaded replies, suggest mode |
| FR7 | Offline editing | Edit offline, sync changes when reconnected (conflict merge) |
| FR8 | Access control | Owner, editor, commenter, viewer roles with sharing links |
| FR9 | Document organization | Folders, search, starring, recent documents |
| FR10 | Auto-save | Every keystroke persisted; no explicit save needed |
| FR11 | Import/Export | Support docx, pdf, html, markdown import and export |
| FR12 | Templates | Pre-built document templates |

## 2. Non-Functional Requirements

| # | NFR | Target |
|---|---|---|
| NFR1 | Availability | 99.99% |
| NFR2 | Latency - local edit | < 16ms (60fps rendering) |
| NFR3 | Latency - remote edit visible | < 200ms (p99) |
| NFR4 | Latency - save confirmation | < 500ms |
| NFR5 | Concurrent editors | Up to 100 simultaneous editors per document |
| NFR6 | Document size | Up to 1.5M characters (equivalent to a 400-page book) |
| NFR7 | Consistency | Strong eventual consistency (all clients converge to same state) |
| NFR8 | Durability | Zero data loss after acknowledgment |
| NFR9 | Scale | 2B documents, 1B users, 50M DAU |
| NFR10 | Offline support | Full editing offline with automatic merge on reconnect |

## 3. Capacity Estimation

### 3.1 Traffic Metrics

| Metric | Value |
|---|---|
| Total documents | 2B |
| DAU | 50M |
| Concurrently active documents | 5M |
| Concurrently editing users | 20M |
| Average operations per user per minute | 30 (typing, formatting) |
| Peak operations/second | 20M users × 0.5 ops/s = 10M ops/s |
| Average collaborators per active document | 3 |
| Document saves (snapshots) per day | 500M |

### 3.2 Storage Estimation

| Data | Calculation | Storage |
|---|---|---|
| Document content (latest) | 2B × 50 KB avg | 100 TB |
| Operation log (30 days) | 10M ops/s × 86400 × 30 × 100 bytes | ~2.6 PB |
| Version snapshots | 500M/day × 30 days × 50 KB | 750 TB |
| Media/images | 2B docs × 5% have images × 2 MB | 200 TB |
| Metadata | 2B × 1 KB | 2 TB |

### 3.3 Network Bandwidth

| Flow | Calculation | Bandwidth |
|---|---|---|
| Operation ingestion | 10M ops/s × 200 bytes | 2 GB/s |
| Operation broadcast (fanout) | 10M ops/s × 3 collaborators × 200 bytes | 6 GB/s |
| Document loads | 1M loads/min × 50 KB | 833 MB/s |
| Snapshot saves | 6K/s × 50 KB | 300 MB/s |

## 4. Data Modeling

### 4.1 Database Selection

| Workload | Database | Justification |
|---|---|---|
| Document metadata | PostgreSQL (sharded) | Relational queries, access control joins |
| Document content (latest state) | Cloud Spanner / CockroachDB | Global strong consistency, large documents |
| Operation log | Cassandra / ScyllaDB | Append-heavy, time-series, high throughput |
| Active session state | Redis Cluster | Sub-ms operations for real-time coordination |
| Version snapshots | S3 + metadata in PostgreSQL | Large blobs, lifecycle management |
| Search index | Elasticsearch | Full-text search across documents |
| Media/images | S3 + CDN | Object storage for embedded media |
| Analytics | ClickHouse | Edit pattern analytics |
| Comments | PostgreSQL | Threaded comments need relational queries |

### 4.2 Schema Design

#### PostgreSQL: Document Metadata
```sql
CREATE TABLE documents (
    document_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id          UUID NOT NULL REFERENCES users(user_id),
    title             VARCHAR(500) DEFAULT 'Untitled document',
    doc_type          VARCHAR(20) DEFAULT 'document', -- document, spreadsheet, presentation
    folder_id         UUID REFERENCES folders(folder_id),
    status            VARCHAR(20) DEFAULT 'active', -- active, trashed, deleted
    current_revision  BIGINT DEFAULT 0,
    word_count        INT DEFAULT 0,
    char_count        INT DEFAULT 0,
    last_edited_by    UUID REFERENCES users(user_id),
    last_edited_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    settings          JSONB DEFAULT '{}',
    version           INT DEFAULT 1
);

CREATE INDEX idx_docs_owner ON documents(owner_id, last_edited_at DESC);
CREATE INDEX idx_docs_folder ON documents(folder_id, title);
CREATE INDEX idx_docs_recent ON documents(last_edited_at DESC) WHERE status = 'active';

CREATE TABLE document_access (
    document_id       UUID REFERENCES documents(document_id),
    user_id           UUID REFERENCES users(user_id),
    role              VARCHAR(20) NOT NULL, -- owner, editor, commenter, viewer
    granted_by        UUID REFERENCES users(user_id),
    granted_at        TIMESTAMP DEFAULT NOW(),
    expires_at        TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (document_id, user_id)
);

CREATE INDEX idx_access_user ON document_access(user_id, role);

CREATE TABLE sharing_links (
    link_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id       UUID REFERENCES documents(document_id),
    role              VARCHAR(20) NOT NULL,
    password_hash     VARCHAR(128),
    expires_at        TIMESTAMP WITH TIME ZONE,
    max_uses          INT,
    current_uses      INT DEFAULT 0,
    created_by        UUID,
    created_at        TIMESTAMP DEFAULT NOW()
);

CREATE TABLE document_comments (
    comment_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id       UUID REFERENCES documents(document_id),
    parent_comment_id UUID REFERENCES document_comments(comment_id),
    author_id         UUID REFERENCES users(user_id),
    content           TEXT NOT NULL,
    anchor_start      INT,            -- position in document
    anchor_end        INT,
    anchor_revision   BIGINT,         -- revision when comment was created
    status            VARCHAR(20) DEFAULT 'open', -- open, resolved, deleted
    created_at        TIMESTAMP DEFAULT NOW(),
    updated_at        TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_comments_doc ON document_comments(document_id, status, created_at);
```

#### Cassandra: Operation Log (Event Sourcing)
```sql
CREATE TABLE document_operations (
    document_id     UUID,
    revision        BIGINT,           -- monotonically increasing per document
    operation_id    UUID,
    user_id         UUID,
    session_id      UUID,
    op_type         TEXT,             -- insert, delete, format, retain
    operation       BLOB,             -- serialized OT operation (Delta format)
    timestamp       TIMESTAMP,
    client_revision BIGINT,           -- revision client was based on
    server_revision BIGINT,           -- assigned server revision
    PRIMARY KEY ((document_id), revision)
) WITH CLUSTERING ORDER BY (revision ASC);

-- For fetching operations since a revision (sync/catchup)
CREATE TABLE document_ops_by_time (
    document_id     UUID,
    day_bucket      DATE,
    revision        BIGINT,
    operation       BLOB,
    user_id         UUID,
    timestamp       TIMESTAMP,
    PRIMARY KEY ((document_id, day_bucket), revision)
) WITH CLUSTERING ORDER BY (revision ASC)
  AND default_time_to_live = 2592000; -- 30 days
```

#### Redis: Active Collaboration State
```
# Active editors for a document
Key: doc:editors:{document_id}
Type: HASH
Fields:
  u_123: {"name":"Alice","color":"#FF6B6B","cursor":{"index":145,"length":0},"ts":1716003600}
  u_456: {"name":"Bob","color":"#4ECDC4","cursor":{"index":289,"length":12},"ts":1716003601}
TTL: None (cleaned on disconnect)

# Document lock (for exclusive operations like restructure)
Key: doc:lock:{document_id}
Value: {user_id, operation, expires_at}
TTL: 30s

# Latest revision counter
Key: doc:rev:{document_id}
Type: INT (INCR for atomic revision assignment)

# Operation queue (pending transforms)
Key: doc:opqueue:{document_id}
Type: LIST (operations awaiting server transform)
```

### 4.3 Indexing Strategy

| Store | Index | Purpose |
|---|---|---|
| PostgreSQL | (owner_id, last_edited_at DESC) | User's recent documents |
| PostgreSQL | (document_id, user_id) on access | Permission checks |
| Cassandra | Partition by document_id, cluster by revision | Sequential operation replay |
| Elasticsearch | Full-text on content + title | Document search |
| Redis | Key by document_id | Real-time state lookup |

## 5. High-Level Design (HLD)

### 5.1 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CLIENT LAYER                                        │
│  [Web App (JS)] [Mobile App (iOS/Android)] [Desktop App (Electron)]         │
│                                                                               │
│  Client Architecture:                                                        │
│  ┌─────────────┐ ┌──────────────┐ ┌───────────────┐ ┌──────────────┐      │
│  │ Editor      │ │ OT Engine    │ │ Offline Queue │ │ WebSocket    │      │
│  │ (ProseMirror│ │ (Transform + │ │ (IndexedDB)  │ │ Client       │      │
│  │  / Quill)   │ │  Compose)    │ │               │ │              │      │
│  └─────────────┘ └──────────────┘ └───────────────┘ └──────────────┘      │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │ WebSocket (real-time ops)
                                    │ HTTPS (REST APIs)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        EDGE LAYER                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌─────────────────────┐   │
│  │ Route 53 │  │ CDN      │  │ WAF          │  │ Application LB (L7) │   │
│  │ (Latency │  │(Static + │  │(Rate limit + │  │ (WebSocket aware,   │   │
│  │  routing)│  │ Doc imgs)│  │ DDoS protect)│  │  sticky sessions)   │   │
│  └──────────┘  └──────────┘  └──────────────┘  └─────────────────────┘   │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
┌───────────────────────────────────┼─────────────────────────────────────────┐
│              COLLABORATION LAYER (Real-time)       │                          │
│                                                     ▼                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              Collaboration Server Cluster                             │   │
│  │                                                                       │   │
│  │  ┌────────────────────────────────────────────────────────────┐     │   │
│  │  │  Document Session Manager                                    │     │   │
│  │  │  • One "session leader" per active document                 │     │   │
│  │  │  • Handles OT transform, revision assignment, broadcast     │     │   │
│  │  │  • Stateful: holds document state in memory during editing  │     │   │
│  │  │  • Consistent hashing: doc_id → session leader node         │     │   │
│  │  └────────────────────────────────────────────────────────────┘     │   │
│  │                                                                       │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │ Collab Node 1│  │ Collab Node 2│  │ Collab Node N│              │   │
│  │  │ (docs A-F)   │  │ (docs G-M)   │  │ (docs ...)   │              │   │
│  │  │ OT Engine    │  │ OT Engine    │  │ OT Engine    │              │   │
│  │  │ WS Conns     │  │ WS Conns     │  │ WS Conns     │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  │                                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
┌───────────────────────────────────┼─────────────────────────────────────────┐
│              APPLICATION LAYER                      │                         │
│                                                     ▼                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │ Document Service │  │ User & Auth      │  │ Comment Service  │         │
│  │ (CRUD, sharing)  │  │ Service          │  │                  │         │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │ Version Service  │  │ Export Service   │  │ Search Service   │         │
│  │ (history, restore│  │ (pdf,docx,html) │  │ (Elasticsearch)  │         │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │ Notification Svc │  │ Template Service │  │ Media Service    │         │
│  │                  │  │                  │  │ (image upload)   │         │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘         │
│                                                                               │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
┌───────────────────────────────────┼─────────────────────────────────────────┐
│                      DATA LAYER                    │                          │
│                                                     ▼                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ PostgreSQL   │  │ Spanner/CRDB │  │ Cassandra    │  │ Redis Cluster│  │
│  │ (Metadata,   │  │ (Document    │  │ (Operation   │  │ (Sessions,   │  │
│  │  Access,     │  │  Content -   │  │  Log - event │  │  Cursors,    │  │
│  │  Comments)   │  │  latest)     │  │  sourcing)   │  │  Locks)      │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ S3           │  │ Elasticsearch│  │ Kafka        │  │ ClickHouse   │  │
│  │ (Snapshots,  │  │ (Full-text   │  │ (Events,     │  │ (Analytics)  │  │
│  │  Media)      │  │  Search)     │  │  Indexing)   │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Core Algorithm: Operational Transformation (OT)

```
┌─────────────────────────────────────────────────────────────────┐
│               OPERATIONAL TRANSFORMATION (OT)                    │
│                                                                   │
│  Problem: Two users edit simultaneously                          │
│                                                                   │
│  Document: "Hello World"                                         │
│  User A: Insert "!" at position 11  → "Hello World!"            │
│  User B: Delete "World" (pos 6-11)  → "Hello "                  │
│                                                                   │
│  Without OT: Applying both naively could corrupt document       │
│  With OT: Transform operations against each other               │
│                                                                   │
│  Transform(InsertAt(11,"!"), Delete(6,5)):                       │
│  → InsertAt(6,"!")  (position adjusted because delete shifted)   │
│                                                                   │
│  Result: "Hello !" (both operations applied correctly)           │
│                                                                   │
│  ┌─────────────────────────────────────────────────────┐        │
│  │  Server OT Algorithm (Jupiter/Google Wave):          │        │
│  │                                                       │        │
│  │  1. Client sends op with client_revision             │        │
│  │  2. Server checks: is client_revision == server_rev? │        │
│  │     YES → Apply directly, increment server_rev      │        │
│  │     NO  → Transform against all ops since client_rev│        │
│  │  3. Assign server_revision to transformed op         │        │
│  │  4. Broadcast transformed op to all other clients    │        │
│  │  5. ACK original client with server_revision         │        │
│  │                                                       │        │
│  └─────────────────────────────────────────────────────┘        │
│                                                                   │
│  Operation Types (Quill Delta format):                           │
│  • retain(n): Skip n characters (no change)                      │
│  • insert(text, attributes): Insert text with formatting         │
│  • delete(n): Delete n characters                                │
│                                                                   │
│  Example Delta:                                                  │
│  [                                                               │
│    {"retain": 5},                                                │
│    {"insert": " beautiful", "attributes": {"bold": true}},      │
│    {"retain": 6},                                                │
│    {"delete": 1}                                                 │
│  ]                                                               │
│  Meaning: Skip 5 chars, insert " beautiful" (bold), skip 6,     │
│           delete 1 character                                      │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## 6. Low-Level Design (LLD)

### 6.1 WebSocket Protocol (Collaboration)

```json
// Client → Server: Submit Operation
{
  "type": "operation",
  "document_id": "doc_abc123",
  "client_revision": 42,
  "operation": {
    "ops": [
      {"retain": 10},
      {"insert": "Hello "},
      {"retain": 50}
    ]
  },
  "cursor_after": {"index": 16, "length": 0},
  "operation_id": "op_xyz789",
  "timestamp": 1716003600000
}

// Server → Client: Operation Acknowledged
{
  "type": "ack",
  "operation_id": "op_xyz789",
  "server_revision": 43
}

// Server → Other Clients: Broadcast Operation
{
  "type": "remote_operation",
  "user_id": "u_123",
  "user_name": "Alice",
  "server_revision": 43,
  "operation": {
    "ops": [
      {"retain": 10},
      {"insert": "Hello "},
      {"retain": 50}
    ]
  },
  "cursor": {"index": 16, "length": 0}
}

// Cursor/Selection Updates (high frequency, unreliable delivery OK)
{
  "type": "cursor",
  "user_id": "u_123",
  "cursor": {"index": 145, "length": 20},
  "timestamp": 1716003600500
}

// Presence
{
  "type": "presence",
  "action": "join",  // join, leave
  "user_id": "u_456",
  "user_name": "Bob",
  "color": "#4ECDC4"
}
```

### 6.2 REST APIs

```http
GET /api/v1/documents/{document_id}
Authorization: Bearer <token>

Response (200 OK):
{
  "document_id": "doc_abc123",
  "title": "Q3 Planning",
  "content": {...},           // Full document Delta
  "revision": 1543,
  "owner": {"user_id": "u_1", "name": "Alice"},
  "collaborators": [
    {"user_id": "u_2", "name": "Bob", "role": "editor", "online": true}
  ],
  "last_edited_at": "2025-05-18T10:00:00Z",
  "word_count": 2450,
  "settings": {...}
}

POST /api/v1/documents/{document_id}/versions
Authorization: Bearer <token>

Request:
{
  "name": "Before major restructure",  // optional named version
  "revision": 1543
}

Response (201):
{
  "version_id": "ver_abc",
  "revision": 1543,
  "name": "Before major restructure",
  "created_at": "2025-05-18T10:00:00Z",
  "snapshot_url": "..."
}

GET /api/v1/documents/{document_id}/history?from_revision=1500&limit=50
Authorization: Bearer <token>

Response (200 OK):
{
  "operations": [
    {
      "revision": 1501,
      "user_id": "u_123",
      "user_name": "Alice",
      "operation": {"ops": [...]},
      "timestamp": "2025-05-18T09:55:00Z"
    },
    ...
  ],
  "has_more": true,
  "next_cursor": "rev_1550"
}
```

### 6.3 Internal gRPC

```protobuf
syntax = "proto3";
package collaboration.v1;

service CollaborationService {
  rpc SubmitOperation(SubmitOperationRequest) returns (SubmitOperationResponse);
  rpc GetDocument(GetDocumentRequest) returns (GetDocumentResponse);
  rpc GetOperationsSince(GetOpsRequest) returns (stream Operation);
  rpc CreateSnapshot(CreateSnapshotRequest) returns (CreateSnapshotResponse);
  rpc RestoreVersion(RestoreVersionRequest) returns (RestoreVersionResponse);
}

service DocumentSessionService {
  rpc JoinSession(JoinSessionRequest) returns (JoinSessionResponse);
  rpc LeaveSession(LeaveSessionRequest) returns (LeaveSessionResponse);
  rpc GetActiveEditors(GetEditorsRequest) returns (GetEditorsResponse);
  rpc TransferSessionLeader(TransferRequest) returns (TransferResponse);
}
```

## 7. Deep Dive: OT Server Implementation

### 7.1 Collaboration Server Node (Stateful)

```python
class DocumentSession:
    """Manages real-time collaboration for a single document"""
    
    def __init__(self, document_id, initial_content, initial_revision):
        self.document_id = document_id
        self.content = initial_content            # Current document state (Delta)
        self.revision = initial_revision           # Server revision counter
        self.pending_ops = []                      # Operations awaiting persistence
        self.clients = {}                          # session_id → ClientState
        self.lock = asyncio.Lock()                # Serialize operation processing
        self.snapshot_interval = 100               # Snapshot every 100 revisions
        self.last_snapshot_rev = initial_revision
    
    async def apply_operation(self, client_id, client_revision, operation):
        """Core OT processing - serialize per document"""
        async with self.lock:
            # 1. Transform against concurrent operations
            if client_revision < self.revision:
                # Client is behind; transform their op against missed ops
                missed_ops = self.get_ops_since(client_revision)
                for missed_op in missed_ops:
                    operation = transform(operation, missed_op)  # OT transform
            elif client_revision > self.revision:
                raise InvalidRevisionError("Client ahead of server")
            
            # 2. Apply to document state
            self.content = apply_delta(self.content, operation)
            self.revision += 1
            
            # 3. Persist to operation log (async but ordered)
            await self.persist_operation(operation, self.revision, client_id)
            
            # 4. Maybe create snapshot
            if self.revision - self.last_snapshot_rev >= self.snapshot_interval:
                await self.create_snapshot()
            
            # 5. Broadcast to other clients
            await self.broadcast(client_id, operation, self.revision)
            
            # 6. ACK the submitting client
            return self.revision

    def get_ops_since(self, revision):
        """Get all operations after the given revision"""
        # First check in-memory buffer, then fall back to Cassandra
        return [op for op in self.pending_ops if op.revision > revision]


def transform(op_a, op_b):
    """
    Transform op_a against op_b so that:
    apply(apply(doc, op_b), transform(op_a, op_b)) == 
    apply(apply(doc, op_a), transform(op_b, op_a))
    
    This is the convergence property (TP1).
    """
    result = []
    i, j = 0, 0
    ops_a, ops_b = op_a.ops, op_b.ops
    
    while i < len(ops_a) or j < len(ops_b):
        # Handle insert vs insert, insert vs retain, delete vs retain, etc.
        # ... (complex transform logic for each operation pair)
        pass
    
    return Delta(result)
```

### 7.2 Snapshot & Recovery Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│              SNAPSHOT & RECOVERY STRATEGY                         │
│                                                                   │
│  Document Recovery Equation:                                     │
│  current_state = last_snapshot + apply(all_ops_since_snapshot)   │
│                                                                   │
│  Snapshot Policy:                                                │
│  • Every 100 operations (configurable)                           │
│  • Every 5 minutes of active editing                             │
│  • On session close (when last editor leaves)                    │
│  • Before version history restore                                │
│                                                                   │
│  Storage:                                                        │
│  • Latest snapshot: Cloud Spanner (fast access)                  │
│  • Historical snapshots: S3 (cost-effective, lifecycle managed)  │
│  • Operation log: Cassandra (30-day retention)                   │
│                                                                   │
│  Recovery Time:                                                  │
│  • Hot path (snapshot + <100 ops): < 50ms                       │
│  • Warm path (S3 snapshot + replay): < 2 seconds                │
│  • Cold path (rebuild from start): Minutes (rare, emergency)    │
│                                                                   │
│  Compaction:                                                     │
│  • After 30 days: delete operation log, keep only snapshots     │
│  • Snapshots: keep daily snapshots for 1 year, then weekly      │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## 8. Component Optimization

### 8.1 WebSocket Optimization

- **Message compression**: Protocol Buffers for OT operations (50% smaller than JSON)
- **Batching**: Client batches keystrokes within 50ms window before sending
- **Cursor throttling**: Cursor updates sent at max 10/second (not every keystroke)
- **Binary frames**: Use WebSocket binary frames for operations
- **Multiplexing**: Single WS connection for ops + cursors + comments (tagged messages)

### 8.2 Kafka (Async Processing)

```yaml
document-operations:
  partitions: 128
  replication.factor: 3
  retention.ms: 2592000000        # 30 days
  partition_strategy: hash(document_id)  # All ops for same doc in same partition
  compression.type: zstd
  
document-events:
  partitions: 32
  # Events: document.created, document.shared, document.exported
  
search-indexing:
  partitions: 64
  # Consumed by Elasticsearch indexer
```

### 8.3 Caching Strategy

```
Redis Cache Layers:

1. Document metadata cache:
   Key: doc:meta:{document_id}
   TTL: 5 minutes
   Invalidation: On metadata update (write-through)

2. Access control cache:
   Key: doc:access:{document_id}:{user_id}
   TTL: 1 minute (short for security)
   Value: {role, permissions}

3. Active session cache:
   Key: doc:session:{document_id}
   TTL: None (managed by session lifecycle)
   Value: {editors, cursors, revision}

4. Document content cache (hot documents):
   Key: doc:content:{document_id}
   TTL: No TTL (invalidated on snapshot)
   Value: Serialized Delta (latest state)
   Size limit: Only cache docs < 1 MB
```

### 8.4 Database Optimization

```sql
-- Spanner: Document content with strongly-consistent reads
-- Interleaved tables for co-located access

CREATE TABLE DocumentContent (
    DocumentId STRING(36) NOT NULL,
    Revision   INT64 NOT NULL,
    Content    BYTES(MAX),        -- Serialized Delta (protobuf)
    ContentHash STRING(64),       -- SHA-256 for integrity
    UpdatedAt  TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp = true),
) PRIMARY KEY (DocumentId);

-- Cassandra: Operation log optimized for sequential reads
-- Partition by document_id for single-partition reads during catchup
-- TTL 30 days automatically drops old operations
-- Compaction: LeveledCompactionStrategy (good for sequential reads)
```

### 8.5 Offline Editing & Conflict Resolution

```
┌─────────────────────────────────────────────────────────────────┐
│              OFFLINE EDITING ARCHITECTURE                         │
│                                                                   │
│  Client (Offline Mode):                                          │
│  1. Store operations in IndexedDB queue                          │
│  2. Apply operations locally (optimistic)                        │
│  3. Track last known server revision                             │
│                                                                   │
│  Reconnection Sync:                                              │
│  1. Client sends: "I was at revision 42, I have 15 pending ops" │
│  2. Server responds: "Server is at revision 58"                  │
│  3. Server sends ops 43-58 to client                             │
│  4. Client transforms its 15 pending ops against ops 43-58      │
│  5. Client submits transformed ops to server                     │
│  6. Server processes normally (may need further transform)       │
│                                                                   │
│  Edge Cases:                                                     │
│  • Two users edit same paragraph offline → OT resolves           │
│  • One user deletes text another edited → insert preserved       │
│  • Conflict too complex → server accepts both, UI shows conflict │
│                                                                   │
│  CRDT Alternative (Automerge/Yjs):                              │
│  • No central server needed for transform                        │
│  • Better offline support (no transform against server ops)      │
│  • Larger state size (metadata overhead)                         │
│  • Trade-off: Simpler conflict resolution but more bandwidth     │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## 9. Observability

### 9.1 Key Metrics

```yaml
# Collaboration Metrics
docs_active_sessions{region}                              # Gauge
docs_concurrent_editors{region}                           # Gauge
docs_operations_per_second{region}                        # Counter rate
docs_operation_transform_count                             # Histogram (how many transforms per op)
docs_operation_latency_ms{phase}                          # Histogram (submit, transform, persist, broadcast)
docs_ot_conflict_rate                                      # Counter (operations requiring transform)

# Document Metrics
docs_document_size_bytes                                   # Histogram
docs_revision_rate{document_id}                           # Counter (edits/minute per doc)
docs_snapshot_creation_duration_ms                         # Histogram
docs_recovery_duration_ms{path}                           # Histogram (hot, warm, cold)

# WebSocket Metrics
docs_ws_connections_active{node}                           # Gauge
docs_ws_message_size_bytes{direction}                      # Histogram
docs_ws_reconnections_total{reason}                        # Counter

# Persistence Metrics
docs_cassandra_write_latency_ms                            # Histogram
docs_spanner_read_latency_ms                               # Histogram
docs_s3_snapshot_upload_duration_ms                        # Histogram
```

### 9.2 Alerting

| Alert | Condition | Severity |
|---|---|---|
| OT transform backlog | >1000 pending transforms per node | P1 |
| Operation latency | p99 > 2 seconds | P1 |
| Session node failure | Node unreachable, sessions need migration | P1 |
| Snapshot lag | Document >500 ops without snapshot | P2 |
| WebSocket reconnection spike | >10% reconnections in 5 min | P2 |
| Cassandra write failure | >1% write errors | P2 |

## 10. Considerations and Assumptions

### 10.1 Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Conflict resolution | OT (Operational Transformation) | Proven at Google scale, lower bandwidth than CRDT |
| Document session model | Stateful collaboration servers | OT requires sequential processing per document |
| Partition strategy | Consistent hashing on document_id | All ops for a doc go to same server |
| Persistence model | Event sourcing (operation log + snapshots) | Complete history, replay capability |
| Content format | Quill Delta | Rich text representation, composable operations |
| Offline support | Queue + transform on reconnect | Eventually consistent merge |

### 10.2 Scalability Considerations

| Challenge | Solution |
|---|---|
| Hot document (1000s of editors) | Shard within document (paragraph-level sessions) |
| Session server failure | Rebuild session from latest snapshot + operation log (< 2s) |
| Very large documents | Chunk-based loading; only load visible sections |
| Cross-region collaboration | Regional collaboration servers with async replication |
| Search indexing at scale | Async indexing via Kafka; eventual consistency for search |
