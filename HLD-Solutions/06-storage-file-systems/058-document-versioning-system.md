# Document Versioning System - System Design

## 1. Requirements

### Functional Requirements
1. Automatic version creation on every save
2. Branching and merging (git-like for documents)
3. Diff computation between any two versions
4. Rollback to any historical version
5. Version labels/tags (e.g., "v2.0 Final", "Approved")
6. Conflict detection during concurrent edits
7. Storage-efficient delta storage (avoid storing full copies)
8. Complete audit trail (who changed what, when)

### Non-Functional Requirements
- Availability: 99.99%
- Version creation: <100ms
- Diff computation: <500ms for documents up to 10MB
- Scale: millions of versions per document
- Storage: 90%+ savings via delta compression
- Concurrent editors: support 50+ per document
- Data retention: indefinite for labeled versions

## 2. Capacity Estimation

| Metric | Value |
|--------|-------|
| Total documents | 5B |
| Avg versions per document | 200 |
| Total versions | 1T |
| New versions/day | 2B |
| Peak version creation QPS | 50K |
| Avg document size | 50 KB |
| Avg delta size | 2 KB (4% of full) |
| Full snapshot frequency | Every 50 versions |
| Total storage (deltas) | 2 PB (vs 50 PB full) |
| Diff requests/day | 500M |
| Branch/merge operations/day | 10M |

### Storage Savings
- Naive (full copy per version): 1T × 50KB = 50 PB
- With delta storage: ~2 PB (96% savings)
- Periodic snapshots overhead: +200 TB
- Total: ~2.2 PB

## 3. Data Modeling

### Documents (PostgreSQL)
```sql
CREATE TABLE documents (
    doc_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id        UUID NOT NULL,
    workspace_id    UUID,
    name            VARCHAR(1024) NOT NULL,
    doc_type        VARCHAR(50) NOT NULL,   -- text, json, binary, rich_text
    current_version_id UUID,
    default_branch  VARCHAR(128) DEFAULT 'main',
    version_count   BIGINT DEFAULT 0,
    total_size      BIGINT DEFAULT 0,
    is_locked       BOOL DEFAULT FALSE,
    locked_by       UUID,
    locked_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_docs_owner ON documents(owner_id, updated_at DESC);
CREATE INDEX idx_docs_workspace ON documents(workspace_id, name);
```

### Versions (DAG structure with parent pointers)
```sql
CREATE TABLE versions (
    version_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id          UUID NOT NULL REFERENCES documents(doc_id),
    branch_id       UUID NOT NULL REFERENCES branches(branch_id),
    version_number  BIGINT NOT NULL,       -- sequential within branch
    
    -- DAG structure
    parent_ids      UUID[] NOT NULL,       -- 1 parent = normal, 2 = merge commit
    
    -- Content storage
    storage_type    VARCHAR(20) NOT NULL,  -- snapshot, forward_delta, reverse_delta
    content_ref     VARCHAR(512) NOT NULL, -- S3 key for content/delta
    content_size    BIGINT NOT NULL,       -- size of stored delta/snapshot
    full_size       BIGINT NOT NULL,       -- size of reconstructed document
    content_hash    VARCHAR(64) NOT NULL,  -- SHA-256 of full content
    
    -- Delta chain management
    base_snapshot_id UUID,                 -- nearest snapshot ancestor
    chain_depth     INT NOT NULL DEFAULT 0, -- distance from base snapshot
    
    -- Metadata
    author_id       UUID NOT NULL,
    message         TEXT,                  -- commit message
    change_summary  JSONB,                 -- { lines_added: 5, lines_deleted: 2, sections_modified: [...] }
    
    -- Labels
    labels          TEXT[],               -- ['v2.0', 'approved', 'release']
    is_labeled      BOOL DEFAULT FALSE,
    
    -- Timestamps
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE (doc_id, branch_id, version_number)
);

CREATE INDEX idx_versions_doc ON versions(doc_id, created_at DESC);
CREATE INDEX idx_versions_branch ON versions(branch_id, version_number DESC);
CREATE INDEX idx_versions_parent ON versions USING GIN(parent_ids);
CREATE INDEX idx_versions_hash ON versions(doc_id, content_hash);
CREATE INDEX idx_versions_labels ON versions USING GIN(labels) WHERE is_labeled = TRUE;
CREATE INDEX idx_versions_base ON versions(base_snapshot_id, chain_depth);
```

### Branches (PostgreSQL)
```sql
CREATE TABLE branches (
    branch_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id          UUID NOT NULL REFERENCES documents(doc_id),
    name            VARCHAR(128) NOT NULL,
    head_version_id UUID,                  -- latest version on this branch
    base_version_id UUID NOT NULL,         -- where branch was created from
    status          VARCHAR(20) DEFAULT 'active',  -- active, merged, deleted
    created_by      UUID NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    merged_at       TIMESTAMPTZ,
    merged_into     UUID,                  -- target branch if merged
    
    UNIQUE (doc_id, name)
);

CREATE INDEX idx_branches_doc ON branches(doc_id, status);
```

### Merge Commits (PostgreSQL)
```sql
CREATE TABLE merge_records (
    merge_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id          UUID NOT NULL,
    source_branch   UUID NOT NULL,
    target_branch   UUID NOT NULL,
    source_version  UUID NOT NULL,
    target_version  UUID NOT NULL,
    result_version  UUID NOT NULL,         -- the merge commit
    ancestor_version UUID NOT NULL,        -- LCA (common ancestor)
    merge_strategy  VARCHAR(30) NOT NULL,  -- auto, manual, theirs, ours
    had_conflicts   BOOL DEFAULT FALSE,
    conflict_data   JSONB,                 -- resolved conflicts detail
    merged_by       UUID NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_merges_doc ON merge_records(doc_id, created_at DESC);
CREATE INDEX idx_merges_branches ON merge_records(source_branch, target_branch);
```

### Audit Trail (Cassandra - append-only, high volume)
```sql
CREATE TABLE version_audit (
    doc_id          UUID,
    event_time      TIMESTAMP,
    event_type      TEXT,          -- create, view, diff, rollback, branch, merge, label
    version_id      UUID,
    user_id         UUID,
    details         TEXT,          -- JSON: additional context
    ip_address      TEXT,
    user_agent      TEXT,
    PRIMARY KEY ((doc_id), event_time, event_type)
) WITH CLUSTERING ORDER BY (event_time DESC);

-- Per-user activity feed
CREATE TABLE user_version_activity (
    user_id         UUID,
    event_time      TIMESTAMP,
    doc_id          UUID,
    event_type      TEXT,
    version_id      UUID,
    PRIMARY KEY ((user_id), event_time)
) WITH CLUSTERING ORDER BY (event_time DESC);
```

### Active Locks (Redis)
```python
# Redis structures for concurrency control
# lock:{doc_id}              → Hash { user_id, branch, timestamp, lock_type }
# editing:{doc_id}:{branch}  → Set of user_ids currently editing
# session:{doc_id}:{user_id} → Hash { branch, last_version, last_activity }
```

## 4. High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CLIENT LAYER                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │  Editor  │  │   CLI    │  │   API    │  │  Review  │                  │
│  │   (Web)  │  │  Client  │  │  Client  │  │   Tool   │                  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘                  │
└───────┼──────────────┼──────────────┼──────────────┼──────────────────────┘
        │              │              │              │
┌───────▼──────────────▼──────────────▼──────────────▼──────────────────────┐
│                    API Gateway                                              │
└──────────────────────────────┬─────────────────────────────────────────────┘
                               │
┌──────────────────────────────┼─────────────────────────────────────────────┐
│                              ▼                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐          │
│  │  Version   │  │   Diff     │  │  Branch    │  │   Merge    │          │
│  │  Service   │  │  Service   │  │  Service   │  │  Service   │          │
│  │            │  │            │  │            │  │            │          │
│  │• Create    │  │• Text diff │  │• Create    │  │• LCA find  │          │
│  │• Retrieve  │  │• Binary    │  │• List      │  │• 3-way merge│          │
│  │• Rollback  │  │• Semantic  │  │• Delete    │  │• Conflict  │          │
│  │• Label     │  │• Render    │  │            │  │  resolve   │          │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘          │
│        │                │               │               │                  │
│  ┌─────▼────────────────▼───────────────▼───────────────▼──────┐          │
│  │                  Internal Service Bus                         │          │
│  └──────────────────────────────┬───────────────────────────────┘          │
│                                 │                                           │
│  ┌──────────────────────────────▼───────────────────────────────┐          │
│  │                     STORAGE LAYER                              │          │
│  │                                                                │          │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │          │
│  │  │PostgreSQL│  │   S3     │  │  Redis   │  │Cassandra │    │          │
│  │  │(Metadata │  │(Deltas + │  │(Locks +  │  │(Audit    │    │          │
│  │  │ + DAG)   │  │Snapshots)│  │ Cache)   │  │  Trail)  │    │          │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │          │
│  └──────────────────────────────────────────────────────────────┘          │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────┐          │
│  │  BACKGROUND WORKERS                                           │          │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │          │
│  │  │  Snapshot   │  │   GC /      │  │  Delta      │         │          │
│  │  │  Creator    │  │  Compaction  │  │  Optimizer  │         │          │
│  │  │  (periodic) │  │             │  │             │         │          │
│  │  └─────────────┘  └─────────────┘  └─────────────┘         │          │
│  └──────────────────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 5. API Design

### Version Operations
```
POST /api/v1/docs/{docId}/versions
  Body: {
    content: "<base64 or text>",
    message: "Updated introduction section",
    branch: "main",
    base_version: "uuid",    # optimistic concurrency check
    labels: ["draft"]
  }
  Response: 201
  {
    version_id: "uuid",
    version_number: 42,
    content_hash: "sha256:abc...",
    change_summary: { lines_added: 5, lines_deleted: 2 },
    created_at: "2025-01-20T10:00:00Z"
  }

GET /api/v1/docs/{docId}/versions?branch=main&limit=50&offset=0
  Response: {
    versions: [
      { version_id, version_number, author, message, created_at, labels, change_summary }
    ],
    total: 1500
  }

GET /api/v1/docs/{docId}/versions/{versionId}
  Response: { version metadata + content }

GET /api/v1/docs/{docId}/versions/{versionId}/content
  Response: raw document content (reconstructed from deltas)

POST /api/v1/docs/{docId}/versions/{versionId}/rollback
  Body: { message: "Reverting to approved version" }
  Response: { new_version_id: "uuid" }  # creates new version with old content
```

### Diff Operations
```
GET /api/v1/docs/{docId}/diff?from={versionA}&to={versionB}&format=unified
  Response: {
    from_version: "uuid",
    to_version: "uuid",
    format: "unified",
    stats: { additions: 15, deletions: 8, modifications: 3 },
    hunks: [
      {
        old_start: 10, old_count: 5,
        new_start: 10, new_count: 7,
        lines: [
          { type: "context", content: "unchanged line" },
          { type: "deletion", content: "removed line" },
          { type: "addition", content: "added line" }
        ]
      }
    ]
  }
```

### Branch Operations
```
POST /api/v1/docs/{docId}/branches
  Body: { name: "feature/new-intro", base_version: "uuid" }
  Response: { branch_id, name, base_version, head_version }

GET /api/v1/docs/{docId}/branches
  Response: { branches: [...] }

POST /api/v1/docs/{docId}/branches/{branchId}/merge
  Body: {
    target_branch: "main",
    strategy: "auto",          # auto, ours, theirs, manual
    message: "Merge feature/new-intro into main"
  }
  Response: {
    merge_version_id: "uuid",
    had_conflicts: false,
    auto_resolved: 3,
    manual_conflicts: 0
  }
```

### Labels
```
POST /api/v1/docs/{docId}/versions/{versionId}/labels
  Body: { labels: ["v2.0", "approved", "release-candidate"] }

GET /api/v1/docs/{docId}/versions?label=approved
  Response: { versions with that label }
```

## 6. Deep Dive: Delta Storage

### Forward vs Reverse Delta Strategy

```python
class DeltaStorageEngine:
    """
    Storage strategy:
    - REVERSE deltas: store the latest version as full snapshot, 
      older versions as reverse diffs from newer.
      Pros: Latest version (most accessed) is fastest to read.
      Cons: Writing new version requires rewriting previous as delta.
    
    - FORWARD deltas: store base snapshot, newer versions as forward diffs.
      Pros: Simple writes (just append delta).
      Cons: Reading latest requires replaying entire chain.
    
    - HYBRID (our choice): 
      Forward deltas with periodic snapshots every N versions.
      Latest read = find nearest snapshot + replay forward deltas.
      Worst case: replay 50 deltas (fast for small docs).
    """
    
    SNAPSHOT_INTERVAL = 50       # Create snapshot every 50 versions
    MAX_CHAIN_DEPTH = 100       # Force snapshot if chain gets too long
    DELTA_ALGORITHM = 'xdelta3'  # For binary; Myers diff for text
    
    async def store_version(self, doc_id: str, branch_id: str, 
                           content: bytes, parent_version_id: str) -> Version:
        """Store new version using optimal delta strategy."""
        
        # Determine if we need a full snapshot
        parent = await self.db.get_version(parent_version_id)
        chain_depth = parent.chain_depth + 1 if parent else 0
        
        need_snapshot = (
            chain_depth >= self.SNAPSHOT_INTERVAL or
            parent is None or
            parent.chain_depth >= self.MAX_CHAIN_DEPTH
        )
        
        if need_snapshot:
            # Store full content
            content_ref = await self._store_snapshot(doc_id, content)
            storage_type = 'snapshot'
            stored_size = len(content)
            chain_depth = 0
            base_snapshot_id = None  # self is the base
        else:
            # Compute and store delta from parent
            parent_content = await self.reconstruct_version(parent_version_id)
            delta = await self._compute_delta(parent_content, content)
            
            content_ref = await self._store_delta(doc_id, delta)
            storage_type = 'forward_delta'
            stored_size = len(delta)
            base_snapshot_id = parent.base_snapshot_id or parent.version_id
        
        # Create version record
        version = Version(
            doc_id=doc_id,
            branch_id=branch_id,
            parent_ids=[parent_version_id] if parent_version_id else [],
            storage_type=storage_type,
            content_ref=content_ref,
            content_size=stored_size,
            full_size=len(content),
            content_hash=hashlib.sha256(content).hexdigest(),
            chain_depth=chain_depth,
            base_snapshot_id=base_snapshot_id
        )
        
        await self.db.insert_version(version)
        return version
    
    async def reconstruct_version(self, version_id: str) -> bytes:
        """Reconstruct full content by replaying delta chain."""
        version = await self.db.get_version(version_id)
        
        if version.storage_type == 'snapshot':
            return await self._read_content(version.content_ref)
        
        # Walk back to nearest snapshot
        chain = []
        current = version
        
        while current.storage_type != 'snapshot':
            chain.append(current)
            # Follow parent pointer (first parent for non-merge commits)
            parent_id = current.parent_ids[0]
            current = await self.db.get_version(parent_id)
        
        # Start from snapshot
        content = await self._read_content(current.content_ref)
        
        # Apply forward deltas in order (oldest to newest)
        for delta_version in reversed(chain):
            delta = await self._read_content(delta_version.content_ref)
            content = await self._apply_delta(content, delta)
        
        # Verify integrity
        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash != version.content_hash:
            raise IntegrityError(
                f"Reconstruction failed: expected {version.content_hash}, got {actual_hash}"
            )
        
        return content
    
    async def _compute_delta(self, old_content: bytes, new_content: bytes) -> bytes:
        """Compute delta using appropriate algorithm."""
        # Detect content type
        if self._is_text(old_content) and self._is_text(new_content):
            return self._text_delta(old_content, new_content)
        else:
            return self._binary_delta(old_content, new_content)
    
    def _text_delta(self, old: bytes, new: bytes) -> bytes:
        """Myers diff algorithm for text content."""
        old_lines = old.decode('utf-8').splitlines(keepends=True)
        new_lines = new.decode('utf-8').splitlines(keepends=True)
        
        # Generate unified diff
        diff = difflib.unified_diff(old_lines, new_lines, n=0)
        delta_text = ''.join(diff)
        
        return zstd.compress(delta_text.encode('utf-8'))
    
    def _binary_delta(self, old: bytes, new: bytes) -> bytes:
        """xdelta3 for binary content (VCDIFF format)."""
        # xdelta3 produces VCDIFF-encoded delta
        result = subprocess.run(
            ['xdelta3', '-e', '-s'],
            input=old + b'\x00SEPARATOR\x00' + new,  # simplified
            capture_output=True
        )
        return result.stdout
    
    async def _apply_delta(self, base: bytes, delta: bytes) -> bytes:
        """Apply delta to base content."""
        # Detect delta type from header
        if delta[:4] == b'\xd6\xc3\xc4\x00':  # VCDIFF magic
            return self._apply_vcdiff(base, delta)
        else:
            # Text delta (unified diff format, zstd compressed)
            diff_text = zstd.decompress(delta).decode('utf-8')
            return self._apply_text_patch(base, diff_text)


class DeltaChainOptimizer:
    """Background worker that optimizes delta chains for read performance."""
    
    async def optimize_chain(self, doc_id: str, branch_id: str):
        """Periodic optimization of delta chains."""
        versions = await self.db.query(
            "SELECT * FROM versions WHERE doc_id = %s AND branch_id = %s "
            "AND storage_type = 'forward_delta' "
            "ORDER BY version_number ASC",
            (doc_id, branch_id)
        )
        
        # Find chains that are too long
        current_chain_length = 0
        for version in versions:
            current_chain_length += 1
            
            if current_chain_length > self.SNAPSHOT_INTERVAL:
                # Create retroactive snapshot
                content = await self.storage_engine.reconstruct_version(version.version_id)
                snapshot_ref = await self.storage_engine._store_snapshot(doc_id, content)
                
                # Update version to be a snapshot
                await self.db.execute(
                    "UPDATE versions SET storage_type = 'snapshot', "
                    "content_ref = %s, chain_depth = 0, base_snapshot_id = NULL "
                    "WHERE version_id = %s",
                    (snapshot_ref, version.version_id)
                )
                
                current_chain_length = 0
    
    async def compact_old_deltas(self, doc_id: str, older_than_days: int = 90):
        """Compact old delta chains into larger snapshots for cold storage."""
        cutoff = datetime.utcnow() - timedelta(days=older_than_days)
        
        # For old versions, increase snapshot interval (less granular)
        # Keep every 200th version as snapshot, discard intermediate deltas
        old_versions = await self.db.query(
            "SELECT * FROM versions WHERE doc_id = %s AND created_at < %s "
            "AND is_labeled = FALSE ORDER BY version_number ASC",
            (doc_id, cutoff)
        )
        
        # Keep snapshots at larger intervals for old data
        for i, version in enumerate(old_versions):
            if i % 200 == 0:
                # Ensure this is a snapshot
                if version.storage_type != 'snapshot':
                    content = await self.storage_engine.reconstruct_version(version.version_id)
                    await self._convert_to_snapshot(version, content)
```

## 7. Deep Dive: Three-Way Merge

### LCA Detection and Merge Algorithm

```python
class ThreeWayMerge:
    """
    Three-way merge for document versions:
    1. Find Lowest Common Ancestor (LCA) of two branches
    2. Compute diff: LCA→source, LCA→target
    3. Apply non-conflicting changes automatically
    4. Detect and report conflicts for manual resolution
    """
    
    async def merge_branches(self, doc_id: str, source_branch_id: str, 
                            target_branch_id: str, strategy: str = 'auto') -> MergeResult:
        """Perform three-way merge between branches."""
        
        # Get branch heads
        source_head = await self._get_branch_head(source_branch_id)
        target_head = await self._get_branch_head(target_branch_id)
        
        # Find LCA (Lowest Common Ancestor)
        ancestor = await self._find_lca(source_head.version_id, target_head.version_id)
        
        if not ancestor:
            raise MergeError("No common ancestor found")
        
        # Reconstruct all three versions
        ancestor_content = await self.storage.reconstruct_version(ancestor.version_id)
        source_content = await self.storage.reconstruct_version(source_head.version_id)
        target_content = await self.storage.reconstruct_version(target_head.version_id)
        
        # Perform three-way merge
        merged_content, conflicts = await self._three_way_merge(
            ancestor_content, source_content, target_content, strategy
        )
        
        if conflicts and strategy == 'auto':
            return MergeResult(
                success=False,
                had_conflicts=True,
                conflicts=conflicts,
                partial_merge=merged_content
            )
        
        # Create merge commit (version with two parents)
        merge_version = await self.storage.store_version(
            doc_id=doc_id,
            branch_id=target_branch_id,
            content=merged_content,
            parent_version_id=target_head.version_id,
            extra_parents=[source_head.version_id],
            message=f"Merge {source_branch_id} into {target_branch_id}"
        )
        
        return MergeResult(
            success=True,
            merge_version_id=merge_version.version_id,
            had_conflicts=len(conflicts) > 0,
            auto_resolved=self._count_auto_resolved(conflicts),
            conflicts_resolved=conflicts if strategy != 'auto' else []
        )
    
    async def _find_lca(self, version_a: str, version_b: str) -> Version:
        """
        Find Lowest Common Ancestor using BFS from both versions.
        This is the equivalent of git merge-base.
        """
        # BFS from both nodes simultaneously
        visited_a = set()
        visited_b = set()
        queue_a = deque([version_a])
        queue_b = deque([version_b])
        
        while queue_a or queue_b:
            # Expand from A
            if queue_a:
                current_a = queue_a.popleft()
                if current_a in visited_b:
                    return await self.db.get_version(current_a)
                visited_a.add(current_a)
                
                parents = await self._get_parents(current_a)
                for parent in parents:
                    if parent not in visited_a:
                        queue_a.append(parent)
            
            # Expand from B
            if queue_b:
                current_b = queue_b.popleft()
                if current_b in visited_a:
                    return await self.db.get_version(current_b)
                visited_b.add(current_b)
                
                parents = await self._get_parents(current_b)
                for parent in parents:
                    if parent not in visited_b:
                        queue_b.append(parent)
        
        return None  # No common ancestor
    
    async def _three_way_merge(self, ancestor: bytes, source: bytes, 
                               target: bytes, strategy: str) -> tuple:
        """
        Three-way merge algorithm:
        - Compute diff(ancestor, source) = changes in source branch
        - Compute diff(ancestor, target) = changes in target branch  
        - Apply non-overlapping changes from both
        - Flag overlapping changes as conflicts
        """
        ancestor_lines = ancestor.decode('utf-8').splitlines(keepends=True)
        source_lines = source.decode('utf-8').splitlines(keepends=True)
        target_lines = target.decode('utf-8').splitlines(keepends=True)
        
        # Compute both diffs
        source_hunks = self._compute_hunks(ancestor_lines, source_lines)
        target_hunks = self._compute_hunks(ancestor_lines, target_lines)
        
        # Merge hunks
        merged_lines = []
        conflicts = []
        
        ancestor_pos = 0
        s_idx, t_idx = 0, 0
        
        while ancestor_pos < len(ancestor_lines) or s_idx < len(source_hunks) or t_idx < len(target_hunks):
            s_hunk = source_hunks[s_idx] if s_idx < len(source_hunks) else None
            t_hunk = target_hunks[t_idx] if t_idx < len(target_hunks) else None
            
            # No more hunks - copy remaining ancestor
            if not s_hunk and not t_hunk:
                merged_lines.extend(ancestor_lines[ancestor_pos:])
                break
            
            # Determine next hunk to process
            next_s = s_hunk.start if s_hunk else float('inf')
            next_t = t_hunk.start if t_hunk else float('inf')
            
            if ancestor_pos < min(next_s, next_t):
                # Copy unchanged lines from ancestor
                end = min(next_s, next_t)
                merged_lines.extend(ancestor_lines[ancestor_pos:end])
                ancestor_pos = end
            elif next_s < next_t:
                # Only source changed this region
                if not self._hunks_overlap(s_hunk, t_hunk):
                    merged_lines.extend(s_hunk.new_lines)
                    ancestor_pos = s_hunk.end
                    s_idx += 1
                else:
                    # Conflict!
                    conflict = self._create_conflict(s_hunk, t_hunk, ancestor_lines)
                    conflicts.append(conflict)
                    
                    if strategy == 'ours':
                        merged_lines.extend(t_hunk.new_lines)
                    elif strategy == 'theirs':
                        merged_lines.extend(s_hunk.new_lines)
                    else:
                        # Include conflict markers
                        merged_lines.append("<<<<<<< target\n")
                        merged_lines.extend(t_hunk.new_lines)
                        merged_lines.append("=======\n")
                        merged_lines.extend(s_hunk.new_lines)
                        merged_lines.append(">>>>>>> source\n")
                    
                    ancestor_pos = max(s_hunk.end, t_hunk.end)
                    s_idx += 1
                    t_idx += 1
            else:
                # Only target changed, or target first
                merged_lines.extend(t_hunk.new_lines)
                ancestor_pos = t_hunk.end
                t_idx += 1
        
        merged_content = ''.join(merged_lines).encode('utf-8')
        return merged_content, conflicts
    
    def _hunks_overlap(self, hunk_a, hunk_b) -> bool:
        """Check if two hunks modify overlapping regions."""
        if hunk_a is None or hunk_b is None:
            return False
        return not (hunk_a.end <= hunk_b.start or hunk_b.end <= hunk_a.start)


class ConflictResolver:
    """Handles conflict resolution strategies."""
    
    async def auto_resolve(self, conflicts: list, doc_type: str) -> list:
        """Attempt automatic conflict resolution for structured documents."""
        resolved = []
        
        for conflict in conflicts:
            if doc_type == 'json':
                # For JSON: merge non-overlapping keys automatically
                resolution = self._merge_json_conflict(conflict)
                if resolution:
                    resolved.append(resolution)
                    continue
            
            elif doc_type == 'rich_text':
                # For rich text: if changes are in different paragraphs, auto-merge
                if self._changes_in_different_blocks(conflict):
                    resolution = self._merge_block_level(conflict)
                    resolved.append(resolution)
                    continue
            
            # Cannot auto-resolve
            resolved.append(ConflictResolution(
                conflict=conflict,
                resolved=False,
                needs_manual=True
            ))
        
        return resolved
```

## 8. Component Optimization

### Read-Path Caching
```python
class VersionCache:
    """Multi-level cache for version content."""
    
    async def get_version_content(self, version_id: str) -> bytes:
        """L1: Redis (hot versions) → L2: Local disk → L3: S3"""
        
        # L1: Redis (latest versions, frequently accessed)
        cached = await self.redis.get(f"vcontent:{version_id}")
        if cached:
            return cached
        
        # L2: Reconstruct from delta chain (with intermediate caching)
        content = await self.storage_engine.reconstruct_version(version_id)
        
        # Cache if version is recent or labeled
        version = await self.db.get_version(version_id)
        if version.is_labeled or version.chain_depth == 0:
            await self.redis.setex(f"vcontent:{version_id}", 3600, content)
        
        return content
```

### Diff Computation Optimization
```python
class DiffService:
    """Optimized diff computation with caching."""
    
    async def compute_diff(self, version_a: str, version_b: str, 
                          format: str = 'unified') -> Diff:
        """Compute diff with result caching."""
        # Check cache (diffs are deterministic)
        cache_key = f"diff:{min(version_a, version_b)}:{max(version_a, version_b)}:{format}"
        cached = await self.redis.get(cache_key)
        if cached:
            return Diff.from_json(cached)
        
        # Reconstruct both versions
        content_a = await self.version_cache.get_version_content(version_a)
        content_b = await self.version_cache.get_version_content(version_b)
        
        # Compute diff using patience algorithm (better for code)
        if self._is_text(content_a):
            diff = self._patience_diff(content_a, content_b)
        else:
            diff = self._binary_diff_summary(content_a, content_b)
        
        # Cache result (1 hour TTL)
        await self.redis.setex(cache_key, 3600, diff.to_json())
        
        return diff
```

## 9. Observability

### Key Metrics
| Metric | Target | Alert |
|--------|--------|-------|
| Version creation latency p99 | <100ms | >500ms |
| Diff computation p99 | <500ms | >2s |
| Delta chain max depth | 50 | >75 |
| Reconstruction latency p99 | <200ms | >1s |
| Merge success rate | >95% auto | <85% |
| Storage efficiency (delta ratio) | >90% | <80% |
| Snapshot creation backlog | <1000 | >10000 |

## 10. Considerations & Trade-offs

| Decision | Choice | Trade-off |
|----------|--------|-----------|
| Delta direction | Forward deltas + periodic snapshots | Simple writes, but reading old versions slower; reverse deltas favor reads but complex writes |
| Delta algorithm | xdelta3 (binary) + Myers (text) | xdelta3 excellent compression but CPU-heavy; simpler diff faster but larger deltas |
| Snapshot interval | Every 50 versions | More snapshots = faster reads but more storage; 50 balances ~96% savings with <200ms reconstruct |
| DAG storage | PostgreSQL arrays for parent_ids | Simple queries but GIN index needed; separate edges table more normalized but extra joins |
| Merge strategy | Three-way with LCA | Standard approach; could use operational merge for structured docs but complex |
| Conflict markers | Git-style inline | Familiar to developers; structured conflict objects better for non-text but harder to render |
| Garbage collection | Keep all labeled, compact unlabeled after 90d | Preserves important versions; could lose intermediate states |
