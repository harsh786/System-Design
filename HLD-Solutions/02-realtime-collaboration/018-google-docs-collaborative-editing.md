# Design Google Docs - Real-Time Collaborative Editing

## 1. Functional Requirements

- **Real-time collaborative editing**: Multiple users editing same document simultaneously
- **Document operations**: Create, read, update, delete documents
- **Rich text formatting**: Bold, italic, headings, lists, tables, images, links
- **Cursor presence**: See other users' cursors and selections in real-time
- **Comments & Suggestions**: Inline comments, suggestion mode, resolve/accept/reject
- **Version history**: Complete history of all changes, restore any version
- **Offline editing**: Work offline, sync when reconnected (conflict resolution)
- **Sharing & permissions**: View, Comment, Edit permissions per user/link
- **Templates**: Pre-built document templates
- **Export/Import**: PDF, DOCX, HTML, Markdown export/import
- **Search**: Full-text search across all user's documents
- **Folder organization**: Folders, shared drives, starred, recent

## 2. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Availability | 99.99% |
| Edit propagation latency | < 100ms between collaborators (same region) |
| Conflict resolution | Automatic, no user intervention needed |
| Consistency | Strong eventual consistency (all users converge) |
| Concurrent editors | Up to 100 simultaneous editors per document |
| Document size | Up to 1.5M characters, unlimited images |
| Version history | Infinite, with snapshot optimization |
| Offline support | Full editing offline, merge on reconnect |
| Scalability | 2B+ documents, 500M+ users |

## 3. Capacity Estimation

| Metric | Value |
|---|---|
| Total users | 500M |
| DAU | 100M |
| Total documents | 5B |
| Active documents (edited/day) | 500M |
| Concurrent open documents | 50M |
| Documents with multiple editors | 10M concurrent |
| Operations/sec (avg) | 5M (keystrokes, formatting) |
| Operations/sec (peak) | 25M |
| Avg document size | 50KB text + 500KB media |
| Storage (documents) | 5B × 100KB = 500 PB |
| Storage (version history) | ~3x document storage = 1.5 EB |
| Bandwidth (operations) | 25M × 200B = 5 GB/s |

## 4. Data Modeling

### Database Selection

| Store | Technology | Purpose |
|---|---|---|
| Document metadata | PostgreSQL (Spanner for global) | ACID, relational, permissions |
| Document content | Custom storage (Colossus/GFS) | Optimized for OT/CRDT operations |
| Operation log | Cassandra / Bigtable | Append-only, high write throughput |
| Version snapshots | Object Storage (GCS/S3) | Periodic full snapshots |
| Real-time state | Redis | Active sessions, cursor positions |
| Search index | Elasticsearch | Full-text document search |
| Media/Images | Object Storage + CDN | Large binary assets |
| Cache | Redis + Memcached | Hot document metadata, permissions |
| Event stream | Kafka | Operation propagation, analytics |

### Schema

```sql
-- Documents
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL,
    title VARCHAR(500),
    type VARCHAR(20), -- document, spreadsheet, presentation
    folder_id UUID,
    current_version BIGINT DEFAULT 0,
    content_snapshot_url TEXT, -- Latest full snapshot in object store
    word_count INT DEFAULT 0,
    last_edited_by UUID,
    last_edited_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    trashed_at TIMESTAMPTZ,
    settings JSONB DEFAULT '{}'
);
CREATE INDEX idx_docs_owner ON documents(owner_id, last_edited_at DESC);
CREATE INDEX idx_docs_folder ON documents(folder_id);

-- Permissions
CREATE TABLE document_permissions (
    document_id UUID REFERENCES documents(id),
    principal_id UUID, -- user_id or group_id
    principal_type VARCHAR(10), -- user, group, anyone
    role VARCHAR(20), -- owner, editor, commenter, viewer
    granted_by UUID,
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (document_id, principal_id)
);
CREATE INDEX idx_perm_principal ON document_permissions(principal_id);

-- Operation Log (Cassandra/Bigtable - append-only)
CREATE TABLE operations (
    document_id UUID,
    version BIGINT,
    user_id UUID,
    session_id UUID,
    op_type VARCHAR(20), -- insert, delete, format, media
    operation BLOB, -- Serialized OT/CRDT operation
    timestamp BIGINT,
    PRIMARY KEY ((document_id), version)
) WITH CLUSTERING ORDER BY (version ASC);

-- Version Snapshots (periodic checkpoints)
CREATE TABLE version_snapshots (
    document_id UUID,
    version BIGINT,
    snapshot_url TEXT, -- Full document state in object store
    delta_from_version BIGINT, -- Previous snapshot version
    created_by UUID,
    title_at_version VARCHAR(500),
    created_at TIMESTAMPTZ,
    PRIMARY KEY ((document_id), version)
) WITH CLUSTERING ORDER BY (version DESC);

-- Comments
CREATE TABLE comments (
    id UUID PRIMARY KEY,
    document_id UUID,
    author_id UUID,
    anchor_start INT, -- Character position start
    anchor_end INT, -- Character position end
    anchor_version BIGINT, -- Version when comment was placed
    content TEXT,
    status VARCHAR(20) DEFAULT 'open', -- open, resolved, deleted
    parent_comment_id UUID, -- For replies
    created_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    resolved_by UUID
);
CREATE INDEX idx_comments_doc ON comments(document_id, status);
```

## 5. High-Level Design

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           CLIENTS                                            │
│  Web App (JS) │ iOS/Android │ Desktop │ API Clients                         │
└───────────────────────────────────┬────────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────────┐
│                         EDGE & API LAYER                                     │
│  ┌────────┐ ┌──────┐ ┌──────────┐ ┌─────────────────────────────────────┐ │
│  │  CDN   │ │ WAF  │ │   LB     │ │          API Gateway                │ │
│  │(static)│ │      │ │(L4+L7)   │ │  - Auth, Rate limit, Routing       │ │
│  └────────┘ └──────┘ └──────────┘ └─────────────────────────────────────┘ │
└───────────────────────────────────┬────────────────────────────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────────┐
         ▼                          ▼                              ▼
┌──────────────────────┐ ┌──────────────────────────┐ ┌──────────────────────┐
│ COLLABORATION SERVER │ │   DOCUMENT SERVICE       │ │  MEDIA SERVICE       │
│ (WebSocket/OT)       │ │   (REST API)             │ │                      │
│                      │ │                          │ │  - Image upload      │
│ - OT Transform       │ │  - CRUD documents        │ │  - Image processing  │
│ - Operation ordering │ │  - Permissions           │ │  - CDN integration   │
│ - Cursor broadcast   │ │  - Sharing               │ │                      │
│ - Conflict resolve   │ │  - Version history       │ │                      │
│ - Session management │ │  - Export/Import         │ │                      │
│                      │ │  - Search                │ │                      │
└──────────┬───────────┘ └──────────┬───────────────┘ └──────────────────────┘
           │                         │
           ▼                         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                     CORE INFRASTRUCTURE                                      │
│                                                                              │
│  ┌───────────────────┐  ┌───────────────────┐  ┌────────────────────────┐  │
│  │ OT/CRDT Engine    │  │ Operation Store   │  │ Snapshot Service       │  │
│  │ - Transform ops   │  │ - Append-only log │  │ - Periodic snapshots   │  │
│  │ - Resolve conflict│  │ - Version counter │  │ - Compaction           │  │
│  │ - State machine   │  │ - Bigtable/Cassan │  │ - Object storage       │  │
│  └───────────────────┘  └───────────────────┘  └────────────────────────┘  │
│                                                                              │
│  ┌───────────────────┐  ┌───────────────────┐  ┌────────────────────────┐  │
│  │ Presence Service  │  │ Comment Service   │  │ Notification Service   │  │
│  │ - Active users    │  │ - Inline comments │  │ - @mentions            │  │
│  │ - Cursor positions│  │ - Suggestions     │  │ - Share notifications  │  │
│  │ - Selections      │  │ - Resolve/Accept  │  │ - Comment alerts       │  │
│  └───────────────────┘  └───────────────────┘  └────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

## 6. Deep Dive: OT (Operational Transformation) vs CRDT

### Operational Transformation (Google Docs uses OT)

```
Core Concept:
- Each edit is an "operation" (insert char at position X, delete at Y)
- When concurrent operations conflict, transform one against the other
- Central server determines canonical ordering

Operation Types:
  Insert(position, char/text)
  Delete(position, length)
  Format(position, length, attributes)
  
Transformation Example:
  User A: Insert("H", pos=0)  → "H|ello" 
  User B: Insert("!", pos=5)  → "Hello|!"
  
  A's op arrives first at server → version 1: "Hello" → "HHello"
  B's op needs transform: original pos=5, but A inserted at 0, so shift to pos=6
  Transformed B: Insert("!", pos=6) → "HHello!"
  
  Result: Both users converge to "HHello!"

Server-Side OT Algorithm:
  1. Client sends operation with base_version (version client's op was based on)
  2. Server checks: if base_version == current_version, apply directly
  3. If base_version < current_version:
     a. Get all operations between base_version and current_version
     b. Transform client's op against each intervening op
     c. Apply transformed op to current state
     d. Increment version
  4. Broadcast transformed op to all other clients
  5. ACK to sender with new version
```

### Why Google chose OT over CRDT:
- OT: Central server = simpler consistency guarantee
- OT: Smaller operation size (just position + content)
- OT: Better for text editing (position-based operations natural)
- CRDT: Better for decentralized/offline-first (no central server needed)
- CRDT: Higher memory overhead (unique IDs per character)

### Collaboration Server Implementation

```
class CollaborationServer:
    def __init__(self, document_id):
        self.document_id = document_id
        self.version = 0
        self.operations_log = []  # Ordered list of all operations
        self.active_sessions = {}  # session_id → {user, cursor, color}
    
    def apply_operation(self, client_op, base_version, session_id):
        # Transform against all ops since base_version
        transformed_op = client_op
        for i in range(base_version, self.version):
            server_op = self.operations_log[i]
            transformed_op = transform(transformed_op, server_op)
        
        # Apply to document state
        self.version += 1
        self.operations_log.append(transformed_op)
        
        # Persist to operation store
        persist_operation(self.document_id, self.version, transformed_op)
        
        # Broadcast to other sessions
        for sid, session in self.active_sessions.items():
            if sid != session_id:
                send_operation(session, transformed_op, self.version)
        
        # ACK to sender
        return ACK(version=self.version)
```

## 7. Low-Level Design - APIs

```
# WebSocket Protocol (Collaboration)
→ {"type": "operation", "ops": [{"type": "insert", "pos": 5, "text": "hello"}], "base_version": 42, "session_id": "s_1"}
← {"type": "ack", "version": 43}
← {"type": "operation", "ops": [...], "version": 44, "user_id": "u_2", "cursor": {"pos": 10}}

→ {"type": "cursor_update", "position": 15, "selection": {"start": 15, "end": 20}}
← {"type": "cursor_broadcast", "user_id": "u_2", "position": 20, "color": "#FF5733"}

# REST APIs
POST /api/v1/documents
Request: {"title": "Untitled", "folder_id": "f_123"}
Response: {"id": "doc_abc", "title": "Untitled", "url": "https://docs.google.com/document/d/doc_abc"}

GET /api/v1/documents/{doc_id}
Response: {"id": "...", "title": "...", "content": {...}, "version": 150, "permissions": [...]}

POST /api/v1/documents/{doc_id}/share
Request: {"email": "user@example.com", "role": "editor"}
Response: {"ok": true}

GET /api/v1/documents/{doc_id}/revisions?limit=50
Response: {"revisions": [{"version": 150, "user": "...", "timestamp": "...", "summary": "Added 3 paragraphs"}]}

POST /api/v1/documents/{doc_id}/restore
Request: {"version": 100}
Response: {"ok": true, "new_version": 151}
```

## 8. Version History & Snapshots

```
Strategy: Operation Log + Periodic Snapshots

Operation Log:
- Every keystroke/edit stored as operation
- 100 edits/minute × 60 min = 6000 ops/hour per active document
- Compact by merging sequential same-user edits (debounce 2s)

Snapshots:
- Take full document snapshot every 1000 operations or every 30 minutes
- Snapshot = complete document state (no ops needed to reconstruct)
- Stored in object storage (S3/GCS)

Loading a historical version:
1. Find nearest snapshot BEFORE target version
2. Replay operations from snapshot version to target version
3. Return reconstructed state

Optimization:
- Named versions: user can name a version ("Final draft")
- Auto-summarize: ML generates change summary for version groups
- Diff visualization: highlight changes between any two versions
```

## 9. Observability

```yaml
Metrics:
  docs_active_documents_total
  docs_concurrent_editors{document_id_bucket}
  docs_operation_latency_seconds{op_type, quantile}
  docs_transform_time_seconds{quantile}
  docs_conflict_resolution_total{type}
  docs_websocket_connections{region}
  docs_snapshot_creation_total
  docs_document_size_bytes{quantile}
  docs_search_latency_seconds{quantile}

Alerts:
  Critical: operation propagation > 500ms, document divergence detected
  Warning: snapshot lag > 2 hours, operation log growth > 100K/doc/day
```

## 10. Considerations

### Trade-offs
| Choice | Benefit | Cost |
|---|---|---|
| OT over CRDT | Lower memory, simpler for text | Requires central server, harder offline |
| Central ordering server | Strong consistency guarantee | Single point for ordering (mitigated by sharding per doc) |
| Operation log + snapshots | Full history, efficient storage | Snapshot creation overhead |
| WebSocket per document | Low latency collaboration | Connection management complexity |

### Offline Support
- Queue operations locally while offline
- On reconnect: send all queued ops with last known base_version
- Server transforms against intervening operations
- Potential: large transform chains if offline for long time
- Optimization: periodic client-side checkpoint for fast rejoin
