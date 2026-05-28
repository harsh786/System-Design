# Design Follow Graph Service

## 1. Problem Statement

Design a scalable uni-directional follow graph service that powers social features like follower/following lists, mutual follow detection, follow suggestions, graph queries ("who follows X that I also follow"), and privacy controls for private accounts. This is a foundational service used by feed generation, notifications, and recommendation systems.

---

## 2. Functional Requirements

1. **Follow/Unfollow**: User A follows User B (uni-directional relationship)
2. **Follower List**: Get all followers of a user (with pagination)
3. **Following List**: Get all users that a user follows (with pagination)
4. **Follower/Following Count**: Fast count retrieval
5. **Mutual Follows**: Detect if two users follow each other
6. **Mutual Friends**: "N mutual followers" between viewer and profile
7. **Follow Suggestions**: "People you may know" based on graph proximity
8. **Graph Queries**: "Followers of X that I follow", "People who follow both X and Y"
9. **Privacy**: Private accounts require follow approval; pending/approved states
10. **Bulk Operations**: Mass follow/unfollow, import contacts
11. **Follow Feed Fan-out Integration**: Notify downstream systems on follow events

---

## 3. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Availability | 99.99% |
| Follow/Unfollow Latency | < 100ms (p95) |
| Follower List Latency | < 50ms (p95) |
| Mutual Follow Check | < 10ms (p95) |
| Scale | 2B users, 500B follow edges |
| Consistency | Strong for follow state, Eventual for counts |
| Fan-out Latency | < 5s from follow to downstream |
| Graph Query Latency | < 200ms for 2-hop queries |

---

## 4. Capacity Estimation

### 4.1 Traffic

```
Total users: 2B
Active users (MAU): 1B
Follow edges: 500B (avg 250 following per user)
Median followers: 150, Mean: 250 (power-law distribution)
Celebrity accounts: 10K users with >10M followers

Follows/day: 500M (new follow events)
Unfollows/day: 100M
Follower list reads/day: 10B
Following list reads/day: 5B
Mutual follow checks/day: 20B
Follow suggestion requests/day: 500M
Graph queries/day: 1B

QPS:
  Follow write: 500M / 86400 ≈ 5,800
  Unfollow write: 100M / 86400 ≈ 1,160
  Total writes: ~7,000 QPS (peak 3x: 21,000)
  
  Follower list read: 10B / 86400 ≈ 116,000
  Mutual check: 20B / 86400 ≈ 232,000
  Total reads: ~350,000 QPS (peak 3x: 1.05M)
```

### 4.2 Storage

```
Edge storage:
  500B edges × (8B follower_id + 8B followee_id + 8B timestamp + 1B status)
  = 500B × 25 bytes = 12.5 TB

Reverse index (followee → followers):
  Same data, different key = 12.5 TB

Count cache:
  2B users × (8B user_id + 4B follower_count + 4B following_count)
  = 2B × 16B = 32 GB

Mutual follow bitmap (for mutual detection):
  Bloom filters per user: 2B × 1KB avg = 2 TB

Follow suggestions cache:
  1B active users × 100 suggestions × 8B = 800 GB

Total: ~30 TB primary storage
```

### 4.3 Bandwidth

```
Writes: 7,000 QPS × 100 bytes avg payload = 700 KB/s
Reads: 350,000 QPS × 2KB avg response (paginated list) = 700 MB/s
Peak reads: 1.05M QPS × 2KB = 2.1 GB/s

Internal (fan-out events): 7,000 follows/sec × 500B event = 3.5 MB/s
```

---

## 5. Data Modeling

### 5.1 Primary Schema (Cassandra / ScyllaDB)

```sql
-- Following list: "Who does user X follow?"
-- Access pattern: Get all users that user_id follows, ordered by time
CREATE TABLE following (
    user_id         BIGINT,
    followed_at     TIMESTAMP,
    followee_id     BIGINT,
    status          TINYINT,          -- 1=active, 2=pending (private account)
    PRIMARY KEY (user_id, followed_at, followee_id)
) WITH CLUSTERING ORDER BY (followed_at DESC, followee_id ASC)
  AND compaction = {'class': 'LeveledCompactionStrategy'}
  AND gc_grace_seconds = 864000;

-- Follower list: "Who follows user X?"
-- Access pattern: Get all followers of user_id, ordered by time
CREATE TABLE followers (
    user_id         BIGINT,
    followed_at     TIMESTAMP,
    follower_id     BIGINT,
    status          TINYINT,
    PRIMARY KEY (user_id, followed_at, follower_id)
) WITH CLUSTERING ORDER BY (followed_at DESC, follower_id ASC)
  AND compaction = {'class': 'LeveledCompactionStrategy'};

-- Follow relationship check: "Does A follow B?"
-- Access pattern: Point lookup for follow state
CREATE TABLE follow_state (
    follower_id     BIGINT,
    followee_id     BIGINT,
    status          TINYINT,          -- 1=active, 2=pending, 3=rejected
    followed_at     TIMESTAMP,
    PRIMARY KEY (follower_id, followee_id)
);

-- Reverse follow state: "Does B follow A?" (for mutual detection)
CREATE TABLE reverse_follow_state (
    followee_id     BIGINT,
    follower_id     BIGINT,
    status          TINYINT,
    followed_at     TIMESTAMP,
    PRIMARY KEY (followee_id, follower_id)
);

-- Pending follow requests (for private accounts)
CREATE TABLE pending_requests (
    user_id         BIGINT,           -- The private account owner
    requester_id    BIGINT,
    requested_at    TIMESTAMP,
    PRIMARY KEY (user_id, requested_at, requester_id)
) WITH CLUSTERING ORDER BY (requested_at DESC, requester_id ASC);
```

### 5.2 Count Store (Redis)

```
Key: counts:{user_id}
Value: HASH {
    followers: INT,
    following: INT,
    pending_in: INT,     -- Pending follow requests received
    pending_out: INT     -- Pending follow requests sent
}
TTL: None (permanent, updated on every follow/unfollow)

Key: mutual:{user_a}:{user_b}  (where a < b for consistency)
Value: 1 (exists) or absent
TTL: 1 hour (cache, recomputed on access)
```

### 5.3 Graph Database (Neo4j / Dgraph - for complex queries)

```cypher
// Node
(:User {id: 12345, is_private: false})

// Relationship
(:User)-[:FOLLOWS {since: timestamp, status: 'active'}]->(:User)

// Indexes
CREATE INDEX FOR (u:User) ON (u.id);

// Example queries:
// Mutual followers between A and viewer
MATCH (viewer:User {id: $viewer_id})-[:FOLLOWS]->(mutual)<-[:FOLLOWS]-(target:User {id: $target_id})
RETURN mutual.id LIMIT 20;

// 2-hop suggestion: friends of friends not yet followed
MATCH (me:User {id: $user_id})-[:FOLLOWS]->(friend)-[:FOLLOWS]->(suggestion)
WHERE NOT (me)-[:FOLLOWS]->(suggestion) AND suggestion.id <> $user_id
RETURN suggestion.id, COUNT(friend) AS mutual_count
ORDER BY mutual_count DESC LIMIT 50;
```

### 5.4 Event Schema (Kafka)

```json
{
  "event_type": "follow.created",
  "follower_id": 12345,
  "followee_id": 67890,
  "status": "active",
  "timestamp": 1700000000000,
  "metadata": {
    "source": "profile_page",
    "is_reciprocal": true
  }
}
```

---

## 6. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                           CLIENTS                                      │
│            (Mobile Apps / Web / Internal Services)                     │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                ┌────────────▼────────────┐
                │      API Gateway        │
                │  (Auth, Rate Limit)     │
                └────────────┬────────────┘
                             │
         ┌───────────────────┼─────────────────────────┐
         │                   │                         │
   ┌─────▼──────┐    ┌──────▼──────┐    ┌────────────▼────────────┐
   │   Follow   │    │   Query     │    │    Suggestion           │
   │   Write    │    │   Service   │    │    Service              │
   │   Service  │    │             │    │                         │
   └─────┬──────┘    └──────┬──────┘    └────────────┬────────────┘
         │                   │                        │
         │            ┌──────▼──────┐          ┌─────▼──────────┐
         │            │  Graph      │          │  ML Ranking    │
         │            │  Query      │          │  (Suggestions) │
         │            │  Engine     │          │                │
         │            └──────┬──────┘          └─────┬──────────┘
         │                   │                       │
   ┌─────▼───────────────────▼───────────────────────▼─────────────┐
   │                        DATA LAYER                              │
   │  ┌───────────┐  ┌─────────┐  ┌─────────┐  ┌──────────────┐ │
   │  │ ScyllaDB  │  │  Redis  │  │  Neo4j  │  │    Kafka     │ │
   │  │(Edges/    │  │(Counts, │  │ (Graph  │  │  (Events)    │ │
   │  │ Lists)    │  │ Cache)  │  │  Queries│  │              │ │
   │  └───────────┘  └─────────┘  └─────────┘  └──────────────┘ │
   │  ┌───────────┐  ┌─────────┐  ┌─────────┐                  │
   │  │ ClickHouse│  │  Flink  │  │  Spark  │                  │
   │  │(Analytics)│  │(Stream) │  │(Batch)  │                  │
   │  └───────────┘  └─────────┘  └─────────┘                  │
   └────────────────────────────────────────────────────────────────┘
         │
   ┌─────▼──────────────────────────────────────┐
   │          DOWNSTREAM CONSUMERS               │
   │  ┌───────────┐  ┌──────────┐  ┌─────────┐ │
   │  │   Feed    │  │Notification│ │  Rec    │ │
   │  │  Service  │  │  Service  │  │ Engine  │ │
   │  └───────────┘  └──────────┘  └─────────┘ │
   └─────────────────────────────────────────────┘
```

---

## 7. Low-Level Design & APIs

### 7.1 Follow Write APIs

```
POST /v1/users/{user_id}/follow
  Body: {target_user_id: 67890}
  Response: {
    status: "following"|"pending",  -- pending for private accounts
    followed_at: timestamp
  }
  Side effects:
    - Write to Cassandra (following, followers, follow_state tables)
    - Update Redis counts
    - Emit Kafka event
    - If mutual: emit mutual_follow event

DELETE /v1/users/{user_id}/follow/{target_user_id}
  Response: {unfollowed: true}
  Side effects:
    - Delete from Cassandra tables
    - Decrement Redis counts
    - Emit unfollow Kafka event

POST /v1/users/{user_id}/follow-requests/{requester_id}/approve
  Response: {approved: true}
  -- Moves from pending to active

POST /v1/users/{user_id}/follow-requests/{requester_id}/reject
  Response: {rejected: true}
```

### 7.2 Follow Read APIs

```
GET /v1/users/{user_id}/followers?cursor=&limit=20
  Response: {
    users[]: {user_id, username, avatar, followed_at, is_following_back},
    total_count, next_cursor
  }

GET /v1/users/{user_id}/following?cursor=&limit=20
  Response: {users[], total_count, next_cursor}

GET /v1/users/{user_id}/follow-state/{target_user_id}
  Response: {
    following: true|false,
    followed_by: true|false,
    is_mutual: true|false,
    status: "active"|"pending"|null
  }
  Latency: <10ms (point lookup in Cassandra + cache)

GET /v1/users/{user_id}/mutual-followers/{target_user_id}?limit=5
  Response: {
    users[]: {user_id, username, avatar},
    total_mutual_count: 23
  }

GET /v1/users/{user_id}/follow-requests?cursor=&limit=20
  Response: {requests[]: {user_id, username, requested_at}, count}
```

### 7.3 Graph Query APIs

```
GET /v1/graph/mutual-connections?user_a={id}&user_b={id}&limit=20
  Response: {mutual_followers[], count}
  Implementation: Neo4j query or Cassandra intersection

GET /v1/graph/followers-who-follow?viewer={id}&target={id}&limit=5
  Response: {users[]}
  -- "Followed by person1, person2, and 3 others you follow"

GET /v1/graph/suggestions/{user_id}?limit=50
  Response: {
    suggestions[]: {
      user_id, username, avatar, reason, mutual_count, score
    }
  }
```

### 7.4 Internal APIs (Service-to-Service)

```
POST /internal/v1/fan-out-targets/{user_id}
  Body: {content_id, content_type}
  Response: {follower_ids[]}  -- Paginated for large follower lists
  -- Used by Feed Service for content distribution

GET /internal/v1/is-following-batch
  Body: {pairs[]: [{follower_id, followee_id}]}
  Response: {results[]: {follower_id, followee_id, following: bool}}
  -- Batch check for feed filtering (privacy)

GET /internal/v1/follower-count/{user_id}
  Response: {count: 1500000}
  -- Used by Feed Service to decide push vs pull fan-out
```

---

## 8. Deep Dive: Graph Storage (Cassandra vs Graph DB)

### 8.1 Cassandra Adjacency List Approach

```
Advantages:
✓ Linear scalability (add nodes = add capacity)
✓ Proven at massive scale (Instagram, Twitter, Discord use this)
✓ Excellent write throughput (500B edges manageable)
✓ Predictable latency (< 5ms for point queries)
✓ Simple operational model

Disadvantages:
✗ Multi-hop queries are expensive (require multiple round-trips)
✗ Set intersection (mutual followers) requires client-side compute
✗ No native graph algorithms (PageRank, community detection)
✗ Fan-out for "friends of friends" queries

Access Patterns and Cassandra Fit:
┌─────────────────────────────┬──────────┬───────────────────────┐
│ Access Pattern              │ Latency  │ Implementation        │
├─────────────────────────────┼──────────┼───────────────────────┤
│ Does A follow B?            │ < 5ms    │ Point read follow_state│
│ Get followers of A (page)   │ < 10ms   │ Range scan followers  │
│ Get following of A (page)   │ < 10ms   │ Range scan following  │
│ Mutual followers of A & B   │ < 50ms   │ Fetch both + intersect│
│ 2-hop: Friends of friends   │ 100-500ms│ Multiple round trips  │
│ PageRank / centrality       │ N/A      │ Not feasible online   │
└─────────────────────────────┴──────────┴───────────────────────┘
```

### 8.2 Dedicated Graph DB Approach (Neo4j / Dgraph)

```
Advantages:
✓ Native multi-hop traversal (2-3 hops in < 50ms)
✓ Built-in graph algorithms (PageRank, Louvain, etc.)
✓ Expressive query language (Cypher)
✓ Efficient mutual friend computation
✓ Pattern matching queries

Disadvantages:
✗ Scaling beyond 1 machine is complex (sharding a graph is hard)
✗ Write throughput limited compared to Cassandra
✗ Operational complexity (JVM tuning, memory management)
✗ Cost: Requires all edges in memory for fast traversal
✗ Not proven at 500B edge scale (max ~50B with careful sharding)

Sharding Strategy (if using Neo4j):
  - Partition users by geography or community (minimize cross-shard edges)
  - 100 shards, each with ~5B edges
  - Cross-shard queries via federation (higher latency)
```

### 8.3 Hybrid Architecture (Chosen Approach)

```
┌─────────────────────────────────────────────────────────────────┐
│                    HYBRID GRAPH STORAGE                           │
│                                                                   │
│  ┌──────────────────────┐    ┌──────────────────────────┐      │
│  │     ScyllaDB          │    │       Neo4j               │      │
│  │  (Primary Store)      │    │  (Graph Query Engine)     │      │
│  │                       │    │                           │      │
│  │  - All 500B edges     │    │  - Hot subgraph (~10B    │      │
│  │  - Follow/unfollow    │    │    edges, active users)  │      │
│  │  - List pagination    │    │  - Multi-hop queries     │      │
│  │  - Point lookups      │    │  - Suggestions           │      │
│  │  - Consistency source │    │  - Mutual computation    │      │
│  │                       │    │  - Graph analytics       │      │
│  └──────────┬────────────┘    └─────────────┬────────────┘      │
│             │                               │                    │
│             └───────────┬───────────────────┘                    │
│                         │                                        │
│                   ┌─────▼─────┐                                  │
│                   │   Kafka   │  Sync: ScyllaDB → Neo4j          │
│                   │  (CDC)    │  Lag: < 5 seconds                │
│                   └───────────┘                                  │
└─────────────────────────────────────────────────────────────────┘

Routing Logic:
  - Simple queries (follow check, list): ScyllaDB (< 10ms)
  - Complex queries (mutual, suggestions, 2-hop): Neo4j (< 200ms)
  - Writes: Always to ScyllaDB first, async replicated to Neo4j
```

### 8.4 Cassandra Partition Sizing for Celebrity Accounts

```
Problem: Celebrity with 100M followers → single partition too large

Solution: Follower list sharding

CREATE TABLE followers_sharded (
    user_id         BIGINT,
    shard_id        INT,              -- 0 to N-1, based on follower count
    followed_at     TIMESTAMP,
    follower_id     BIGINT,
    PRIMARY KEY ((user_id, shard_id), followed_at, follower_id)
) WITH CLUSTERING ORDER BY (followed_at DESC, follower_id ASC);

Shard allocation:
  - Users with < 100K followers: 1 shard (shard_id = 0)
  - Users with 100K - 1M: 10 shards
  - Users with 1M - 10M: 100 shards  
  - Users with > 10M: 1000 shards

Shard assignment on write:
  shard_id = hash(follower_id) % num_shards_for_user

Reading full list: Scatter-gather across all shards (parallel queries)
Random sample: Query random shard_id (fast approximation)
Count: From Redis (not from scanning all shards)
```

---

## 9. Deep Dive: Efficient Fan-Out with the Graph

### 9.1 Push vs Pull Model

```
When user creates content, who should see it?
→ Need to notify all followers (fan-out)

┌──────────────────────────────────────────────────────────────┐
│                  FAN-OUT STRATEGY                              │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  PUSH (Fan-out on Write):                                     │
│  - On post: Write to ALL followers' feeds                     │
│  - Pros: Read is O(1), instant feed load                     │
│  - Cons: Celebrity posts → millions of writes                │
│  - Good for: Users with < 10K followers                      │
│                                                                │
│  PULL (Fan-out on Read):                                      │
│  - On post: Write only to author's timeline                  │
│  - On read: Merge posts from all followed users              │
│  - Pros: No write amplification for celebrities              │
│  - Cons: Read is O(following_count), slower feed load        │
│  - Good for: Celebrity accounts (> 10K followers)            │
│                                                                │
│  HYBRID (Chosen):                                             │
│  - Push for users with < 10K followers (99% of users)        │
│  - Pull for celebrities (top 1%) at read time                │
│  - Threshold dynamically adjusted based on system load       │
│                                                                │
└──────────────────────────────────────────────────────────────┘
```

### 9.2 Fan-Out Service Implementation

```python
class FanOutService:
    """
    Distributes content to followers' feeds.
    Called when a user creates a post/pin/tweet.
    """
    
    PUSH_THRESHOLD = 10_000  # Followers below this: push
    
    def __init__(self):
        self.graph_service = FollowGraphClient()
        self.feed_store = FeedStore()  # Redis sorted sets
        self.kafka = KafkaProducer()
    
    async def fan_out(self, author_id: int, content_id: str, created_at: int):
        """Main fan-out entry point."""
        
        follower_count = await self.graph_service.get_follower_count(author_id)
        
        if follower_count <= self.PUSH_THRESHOLD:
            # Push model: Write to all followers' feeds
            await self.push_fan_out(author_id, content_id, created_at)
        else:
            # Hybrid: Push to active followers, mark as pull for rest
            await self.hybrid_fan_out(author_id, content_id, created_at)
    
    async def push_fan_out(self, author_id, content_id, created_at):
        """Push content to all followers' feed caches."""
        
        cursor = None
        while True:
            # Fetch followers in pages (from ScyllaDB)
            page = await self.graph_service.get_followers(
                author_id, cursor=cursor, limit=5000
            )
            
            if not page.followers:
                break
            
            # Batch write to followers' feed caches
            pipe = self.feed_store.redis.pipeline()
            for follower_id in page.followers:
                feed_key = f"feed:{follower_id}"
                pipe.zadd(feed_key, {content_id: created_at})
                pipe.zremrangebyrank(feed_key, 0, -1001)  # Keep top 1000
            await pipe.execute()
            
            cursor = page.next_cursor
            if not cursor:
                break
    
    async def hybrid_fan_out(self, author_id, content_id, created_at):
        """For celebrities: push to active followers only."""
        
        # Get recently active followers (last 7 days)
        active_followers = await self.graph_service.get_active_followers(
            author_id, active_within_days=7
        )
        
        # Push to active followers only (typically 10-30% of total)
        pipe = self.feed_store.redis.pipeline()
        for follower_id in active_followers:
            feed_key = f"feed:{follower_id}"
            pipe.zadd(feed_key, {content_id: created_at})
            pipe.zremrangebyrank(feed_key, 0, -1001)
        await pipe.execute()
        
        # For inactive followers: They'll pull from celebrity timeline on next login
        # Mark author as "celebrity" in their following list metadata
        # Feed generation service will merge celebrity posts at read time
    
    async def handle_new_follow(self, follower_id, followee_id):
        """When user follows someone, backfill their feed with recent content."""
        
        # Get followee's recent posts (last 50)
        recent_posts = await self.get_recent_posts(followee_id, limit=50)
        
        # Add to follower's feed
        pipe = self.feed_store.redis.pipeline()
        feed_key = f"feed:{follower_id}"
        for post in recent_posts:
            pipe.zadd(feed_key, {post.content_id: post.created_at})
        pipe.zremrangebyrank(feed_key, 0, -1001)
        await pipe.execute()
```

### 9.3 Fan-Out Performance Optimization

```
Optimization Techniques:

1. Parallel scatter:
   - Split follower list into chunks of 5,000
   - Process chunks in parallel (10 workers)
   - 10K followers: 2 chunks × 5ms = 10ms total (vs 20ms sequential)

2. Priority fan-out:
   - Close friends / frequent interactors get content first
   - Remaining followers get content within 5 seconds
   - Reduces perceived latency for important relationships

3. Lazy fan-out for inactive users:
   - Users not active in 30 days: Skip push entirely
   - On their next login: Rebuild feed from followed users' timelines
   - Saves 40% of fan-out writes

4. Batch compression:
   - Multiple posts within 1 minute from same user: Single fan-out batch
   - Reduces write amplification for rapid posters

5. Pre-computed fan-out lists:
   - Cache follower_ids in Redis sorted set (by activity score)
   - Avoid hitting ScyllaDB for every fan-out
   - Refresh cache every hour or on follow/unfollow
```

---

## 10. Deep Dive: Graph Analytics (PageRank, Community Detection)

### 10.1 Offline Graph Analytics Pipeline

```
┌───────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────┐
│ ScyllaDB  │────►│  Spark ETL   │────►│  GraphX /    │────►│ Results │
│ (edges)   │     │  (Export)    │     │  Pregel      │     │  Store  │
└───────────┘     └──────────────┘     └──────────────┘     └─────────┘
                                                                  │
                                              ┌───────────────────▼──────┐
                                              │  Applications:            │
                                              │  - User ranking          │
                                              │  - Community clusters    │
                                              │  - Spam detection        │
                                              │  - Influence scoring     │
                                              └──────────────────────────┘
```

### 10.2 PageRank Implementation

```python
class FollowGraphPageRank:
    """
    Compute PageRank on the follow graph to identify influential users.
    Used for:
    - Search ranking (more authoritative users rank higher)
    - Follow suggestions (suggest high-PageRank users)
    - Spam detection (low PageRank + high activity = suspicious)
    - Verified account prioritization
    """
    
    def compute_pagerank(self, spark_context):
        """
        Run on Spark GraphX, weekly batch job.
        Input: 500B edges from ScyllaDB export
        Output: PageRank score per user
        """
        
        # Load edges from Parquet (exported from ScyllaDB nightly)
        edges = spark_context.read.parquet("s3://graph-exports/edges/latest/")
        # Schema: (follower_id: Long, followee_id: Long)
        
        # Build graph
        graph = GraphFrame(vertices=users_df, edges=edges)
        
        # Run PageRank (iterative, damping=0.85, tolerance=0.01)
        results = graph.pageRank(
            resetProbability=0.15,
            tol=0.01,
            maxIter=20
        )
        
        # Output: DataFrame with (user_id, pagerank_score)
        results.vertices.select("id", "pagerank") \
            .write.parquet("s3://graph-analytics/pagerank/latest/")
        
        # Also write to Redis for online serving
        top_users = results.vertices.orderBy(desc("pagerank")).limit(1_000_000)
        write_to_redis(top_users, key_prefix="pr:")
    
    def personalized_pagerank(self, user_id, spark_context):
        """
        Personalized PageRank from a specific user's perspective.
        Used for: "Who is most relevant to ME?"
        Resets random walk back to source user with probability 0.15.
        """
        results = graph.pageRank(
            resetProbability=0.15,
            sourceId=user_id,
            tol=0.01,
            maxIter=10
        )
        return results.vertices.orderBy(desc("pagerank")).limit(100)
```

### 10.3 Community Detection (Louvain Algorithm)

```python
class CommunityDetection:
    """
    Detect communities/clusters in the follow graph.
    Used for:
    - Topic/interest clustering (users in same community share interests)
    - Follow suggestions (suggest from same community)
    - Content recommendations (content popular in user's community)
    - Spam ring detection (tight clusters with suspicious behavior)
    """
    
    def detect_communities(self, spark_context):
        """
        Louvain method for community detection.
        Weekly batch job on Spark GraphX.
        """
        
        edges = spark_context.read.parquet("s3://graph-exports/edges/latest/")
        
        # Convert to undirected for community detection
        # (mutual follows = stronger signal)
        mutual_edges = edges.alias("a").join(
            edges.alias("b"),
            (col("a.follower_id") == col("b.followee_id")) &
            (col("a.followee_id") == col("b.follower_id"))
        ).select(col("a.follower_id"), col("a.followee_id"))
        
        # Run Louvain (or Label Propagation as simpler alternative)
        graph = GraphFrame(vertices=users_df, edges=mutual_edges)
        communities = graph.labelPropagation(maxIter=10)
        
        # Output: (user_id, community_id)
        communities.write.parquet("s3://graph-analytics/communities/latest/")
        
        # Index in Redis for online queries
        # Key: community:{user_id} → community_id
        # Key: community_members:{community_id} → SET of user_ids
    
    def detect_spam_rings(self):
        """
        Find tightly connected clusters with suspicious patterns:
        - High internal edge density
        - Low external connections
        - Similar account creation dates
        - Coordinated behavior (follow same targets simultaneously)
        """
        suspicious = communities.filter(
            (col("internal_density") > 0.8) &
            (col("external_ratio") < 0.1) &
            (col("avg_account_age_days") < 30) &
            (col("size") > 5) & (col("size") < 100)
        )
        return suspicious
```

### 10.4 Follow Suggestions Using Graph

```python
class FollowSuggestionEngine:
    """
    Generate follow suggestions using multiple signals:
    1. Graph proximity (friends of friends)
    2. Community membership
    3. Interest overlap
    4. PageRank (popular users)
    5. Contact import matches
    """
    
    def generate_suggestions(self, user_id, limit=50):
        # Source 1: Friends of friends (Neo4j, real-time)
        fof = self.neo4j.query("""
            MATCH (me:User {id: $user_id})-[:FOLLOWS]->(friend)-[:FOLLOWS]->(suggestion)
            WHERE NOT (me)-[:FOLLOWS]->(suggestion) 
              AND suggestion.id <> $user_id
              AND suggestion.is_private = false
            RETURN suggestion.id, COUNT(DISTINCT friend) AS mutual_count
            ORDER BY mutual_count DESC
            LIMIT 100
        """, user_id=user_id)
        
        # Source 2: Same community members (from batch analytics)
        community_id = self.redis.get(f"community:{user_id}")
        community_members = self.redis.srandmember(
            f"community_members:{community_id}", 50
        )
        
        # Source 3: High PageRank users in followed topics
        user_topics = self.get_user_topics(user_id)
        influential = self.get_top_pagerank_in_topics(user_topics, limit=30)
        
        # Source 4: Contact graph (phone/email matches)
        contacts = self.get_contact_matches(user_id)
        
        # Merge and rank
        candidates = self.merge_sources(fof, community_members, influential, contacts)
        
        # Remove already-following and blocked users
        following = self.get_following_set(user_id)
        blocked = self.get_blocked_set(user_id)
        candidates = [c for c in candidates if c.id not in following and c.id not in blocked]
        
        # ML ranking model
        features = self.extract_features(user_id, candidates)
        scores = self.ranking_model.predict(features)
        
        # Sort by score, add explanations
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        
        return [{
            'user_id': c.id,
            'score': s,
            'reason': self.get_reason(c, user_id),  # "Followed by 5 people you follow"
            'mutual_count': c.mutual_count
        } for c, s in ranked[:limit]]
    
    def get_reason(self, candidate, viewer_id):
        """Generate human-readable suggestion reason."""
        if candidate.source == 'fof':
            return f"Followed by {candidate.mutual_count} people you follow"
        elif candidate.source == 'community':
            return "Similar interests"
        elif candidate.source == 'pagerank':
            return "Popular in topics you follow"
        elif candidate.source == 'contacts':
            return "From your contacts"
```

---

## 11. Component Architecture

### 11.1 Kafka Configuration

```
Topics:
  - follow.events (600M/day) → partitions: 128, retention: 7d
    Key: followee_id (for ordered processing per user)
  - follow.suggestions.refresh → partitions: 64, retention: 1d
  - graph.analytics.results → partitions: 32, retention: 30d
  - follow.fanout.commands → partitions: 256, retention: 1d

Consumer Groups:
  - feed-fanout: follow.events → Add author to follower's feed sources
  - notification-service: follow.events → "X started following you"
  - neo4j-sync: follow.events → Update graph DB
  - counter-updater: follow.events → Update Redis follower counts
  - suggestion-invalidator: follow.events → Invalidate suggestion cache
  - analytics-writer: follow.events → ClickHouse
  - spam-detector: follow.events → Detect follow spam patterns
```

### 11.2 Redis Architecture

```
Cluster: 100 nodes, 5 TB memory

Data Distribution:
1. Follower/Following counts: 2B × 16B = 32 GB
   Key: counts:{user_id} → HASH {followers, following}
   
2. Mutual follow cache: Bloom filter approach
   Key: mutual_bf:{user_id} → Bloom filter of mutual follows
   Size: ~1KB per active user (1% false positive rate)
   Total: 1B × 1KB = 1 TB
   
3. Feed cache (from fan-out): 
   Key: feed:{user_id} → ZSET (content_id → timestamp)
   Size: 1000 items × 20B = 20KB per user
   Active users: 500M × 20KB = 10 TB (exceeds single cluster)
   → Separate Redis cluster for feeds

4. Suggestion cache:
   Key: suggestions:{user_id} → LIST of user_ids
   Size: 50 × 8B = 400B per user
   TTL: 24 hours
   Total: 1B × 400B = 400 GB

5. Active follower sets (for hybrid fan-out):
   Key: active_followers:{user_id} → SET (sampled)
   Only for users with >10K followers
   Size: 10K × 8B = 80KB per celebrity
   Count: 1M celebrities × 80KB = 80 GB
```

### 11.3 ScyllaDB Configuration

```
Cluster: 200 nodes (i3.4xlarge)
  - RF: 3
  - Consistency: LOCAL_QUORUM for writes, LOCAL_ONE for reads
  - Compaction: Leveled (for read-heavy workload)
  - Total storage: 30 TB with replication

Keyspace:
  CREATE KEYSPACE follow_graph WITH replication = {
    'class': 'NetworkTopologyStrategy',
    'us-east': 3,
    'us-west': 3,
    'eu-west': 3
  };

Performance:
  - Write: 21K QPS / 200 nodes = 105 writes/sec/node (well within limits)
  - Read: 350K QPS / 200 nodes (×3 RF reads) = 5,250 reads/sec/node
  - p99 read latency: < 10ms (SSD-backed, data fits in cache for hot users)
```

### 11.4 Neo4j Configuration

```
Cluster: 10 servers (high-memory, 512GB RAM each)
  - Causal cluster (1 leader + 2 followers per core group)
  - 3 read replicas for query scaling
  - Total edges in graph: ~10B (hot subgraph of active users)

Memory allocation:
  - Heap: 64GB
  - Page cache: 400GB (fits most of the graph in memory)
  - Transaction memory: 32GB

Sync from ScyllaDB:
  - Kafka consumer writes to Neo4j in batches of 1000 edges
  - Lag: < 5 seconds from ScyllaDB write to Neo4j availability
  - Only syncs active users (logged in within 90 days)

Query performance:
  - 1-hop (direct followers): < 5ms
  - 2-hop (friends of friends): < 50ms
  - Mutual friends between two users: < 30ms
  - Shortest path (up to 4 hops): < 100ms
```

---

## 12. Privacy & Private Accounts

### 12.1 Follow Request Flow

```
┌────────┐     ┌──────────────┐     ┌──────────────────┐
│ User A │────►│ Follow API   │────►│ Is target private?│
│ follows│     │              │     └────────┬─────────┘
│ User B │     └──────────────┘              │
└────────┘                           ┌───────▼────────┐
                                     │   YES    │  NO  │
                                     └───┬──────┴──┬───┘
                                         │         │
                                    ┌────▼───┐  ┌──▼──────────┐
                                    │ Create │  │ Create       │
                                    │ Pending│  │ Active       │
                                    │ Request│  │ Follow       │
                                    └────┬───┘  └─────────────┘
                                         │
                                    ┌────▼───────────────┐
                                    │ Notify User B      │
                                    │ "A wants to follow"│
                                    └────┬───────────────┘
                                         │
                              ┌──────────▼──────────┐
                              │  User B decides:    │
                              │  Approve / Reject   │
                              └──────────┬──────────┘
                                         │
                              ┌──────────▼──────────┐
                              │ If approved:        │
                              │ Move pending→active │
                              │ Notify A            │
                              │ Update counts       │
                              └─────────────────────┘
```

### 12.2 Privacy Enforcement

```python
class PrivacyEnforcer:
    """Enforces privacy rules across all graph queries."""
    
    def filter_follower_list(self, user_id, viewer_id, followers):
        """Filter follower list based on privacy settings."""
        user = get_user(user_id)
        
        if not user.is_private:
            return followers  # Public account, show all
        
        if viewer_id == user_id:
            return followers  # Owner sees everything
        
        if self.is_following(viewer_id, user_id):
            return followers  # Approved follower sees the list
        
        return []  # Non-follower of private account sees nothing
    
    def can_view_content(self, viewer_id, author_id):
        """Check if viewer can see author's content."""
        author = get_user(author_id)
        
        if not author.is_private:
            return True
        
        return self.is_following(viewer_id, author_id)
    
    def handle_privacy_change(self, user_id, new_is_private):
        """When user switches to private or public."""
        if new_is_private:
            # Existing followers remain; no action needed
            # Future follows require approval
            pass
        else:
            # Switching to public: Approve all pending requests
            pending = get_pending_requests(user_id)
            for request in pending:
                approve_follow(user_id, request.requester_id)
```

---

## 13. Mutual Follow Detection

### 13.1 Real-Time Mutual Check

```python
class MutualFollowDetector:
    """
    Efficiently detect if two users follow each other.
    Called billions of times per day (for UI indicators).
    """
    
    def __init__(self):
        self.redis = RedisCluster()
        self.cassandra = CassandraClient()
    
    async def is_mutual(self, user_a, user_b) -> bool:
        """Check if A follows B AND B follows A."""
        
        # Strategy 1: Redis cache check first
        cache_key = f"mutual:{min(user_a, user_b)}:{max(user_a, user_b)}"
        cached = await self.redis.get(cache_key)
        if cached is not None:
            return cached == b'1'
        
        # Strategy 2: Parallel Cassandra lookups
        a_follows_b, b_follows_a = await asyncio.gather(
            self.cassandra.execute(
                "SELECT status FROM follow_state WHERE follower_id=? AND followee_id=?",
                [user_a, user_b]
            ),
            self.cassandra.execute(
                "SELECT status FROM follow_state WHERE follower_id=? AND followee_id=?",
                [user_b, user_a]
            )
        )
        
        is_mutual = (
            a_follows_b and a_follows_b[0].status == 1 and
            b_follows_a and b_follows_a[0].status == 1
        )
        
        # Cache result (1 hour TTL)
        await self.redis.setex(cache_key, 3600, b'1' if is_mutual else b'0')
        
        return is_mutual
    
    async def get_mutual_followers(self, user_a, user_b, limit=20):
        """Find users that both A and B follow (or that follow both)."""
        
        # For users with small following lists: Set intersection in memory
        if await self.get_following_count(user_a) < 5000 and \
           await self.get_following_count(user_b) < 5000:
            following_a = await self.get_following_set(user_a)
            following_b = await self.get_following_set(user_b)
            mutuals = following_a & following_b
            return list(mutuals)[:limit]
        
        # For large lists: Use Neo4j (pre-computed)
        return await self.neo4j_query(
            "MATCH (a:User {id:$a})-[:FOLLOWS]->(m)<-[:FOLLOWS]-(b:User {id:$b}) "
            "RETURN m.id LIMIT $limit",
            a=user_a, b=user_b, limit=limit
        )
```

### 13.2 Bloom Filter Optimization

```python
class MutualBloomFilter:
    """
    Maintain Bloom filter per user of their followers.
    Enables O(1) "probably follows" check before expensive DB lookup.
    """
    
    BITS_PER_USER = 8192  # 1KB per user, 1% FP rate for 500 items
    HASH_FUNCTIONS = 7
    
    def on_follow(self, followee_id, follower_id):
        """Add follower to followee's Bloom filter."""
        key = f"bf:followers:{followee_id}"
        for i in range(self.HASH_FUNCTIONS):
            bit_pos = mmh3.hash(str(follower_id), i) % self.BITS_PER_USER
            self.redis.setbit(key, bit_pos, 1)
    
    def might_follow(self, followee_id, follower_id) -> bool:
        """Fast probabilistic check: does follower follow followee?"""
        key = f"bf:followers:{followee_id}"
        for i in range(self.HASH_FUNCTIONS):
            bit_pos = mmh3.hash(str(follower_id), i) % self.BITS_PER_USER
            if not self.redis.getbit(key, bit_pos):
                return False  # Definitely does NOT follow
        return True  # Probably follows (verify with DB)
    
    def check_mutual(self, user_a, user_b) -> str:
        """
        Returns: 'definitely_not', 'possible', 'likely'
        """
        a_might_follow_b = self.might_follow(user_b, user_a)
        b_might_follow_a = self.might_follow(user_a, user_b)
        
        if not a_might_follow_b or not b_might_follow_a:
            return 'definitely_not'  # No DB query needed!
        
        return 'possible'  # Need to verify with DB
```

---

## 14. Observability

### 14.1 Key Metrics

```
Business Metrics:
  - Follows/day, Unfollows/day
  - Follow-back rate (% of follows that become mutual)
  - Suggestion acceptance rate
  - Average followers per user (distribution)
  - Celebrity follower growth rate
  - Private account follow request approval rate

System Metrics:
  - Follow write latency (p50/p95/p99)
  - Follower list read latency
  - Mutual check latency
  - Fan-out completion time (p95)
  - Neo4j query latency by query type
  - ScyllaDB partition sizes (detect hot partitions)
  - Kafka consumer lag per group
  - Redis memory usage and eviction rate

SLOs:
  - Follow/Unfollow: 99.99% < 100ms
  - Follower list: 99.9% < 50ms
  - Mutual check: 99.9% < 10ms
  - Suggestions: 99% < 200ms
  - Fan-out (10K followers): 99% < 5s
  - Graph sync lag (ScyllaDB → Neo4j): p99 < 10s
```

### 14.2 Alerting

```yaml
alerts:
  - name: follow_write_latency
    condition: p99 > 200ms for 3 min
    severity: P1

  - name: fanout_lag
    condition: kafka_lag(follow.fanout.commands) > 1M
    severity: P1

  - name: neo4j_sync_lag
    condition: lag_seconds > 30
    severity: P2

  - name: celebrity_partition_hot
    condition: scylla_partition_read_latency_p99 > 50ms
    severity: P2

  - name: suggestion_stale
    condition: cache_age > 48h for >10% users
    severity: P3

  - name: spam_follow_wave
    condition: follow_rate_from_new_accounts > 10x baseline
    severity: P1
```

---

## 15. Key Considerations

### 15.1 Consistency Model
- Follow state: Strongly consistent (user expects immediate feedback)
- Counts: Eventually consistent (< 5s lag acceptable, avoid hot counters)
- Fan-out: Eventually consistent (feed delay < 5s acceptable)
- Suggestions: Stale for up to 24 hours (batch recomputed)

### 15.2 Handling Celebrity Accounts
- Separate shard strategy (partition followers across 1000 shards)
- Pull-based fan-out (don't push to 100M followers)
- Cached follower count (avoid counting 100M rows)
- Follower list sampling (show random subset, not all)

### 15.3 Anti-Spam
- Follow rate limits: Max 200 follows/day, 50/hour
- New account restrictions: Max 20 follows in first 24 hours
- Pattern detection: Coordinated follow campaigns (Flink job)
- Block/mute propagation: Blocked user can't follow

### 15.4 Data Deletion (GDPR)
- User deletion: Remove all follow edges (both directions)
- Tombstone propagation in Cassandra (gc_grace_seconds = 10 days)
- Cascade: Remove from Neo4j, Redis, all caches
- Right to be forgotten: Purge from analytics after 30 days

### 15.5 Migration Strategy
- If migrating from MySQL to Cassandra:
  - Dual-write period (write to both, read from MySQL)
  - Background migration of historical data
  - Gradual read traffic shift (1% → 10% → 100%)
  - Verify consistency with shadow reads

---

## 16. Summary

| Component | Technology | Scale |
|---|---|---|
| Edge Storage | ScyllaDB | 500B edges, 12.5 TB, 200 nodes |
| Graph Queries | Neo4j | 10B hot edges, 10 servers |
| Counts + Cache | Redis Cluster | 100 nodes, 5 TB |
| Event Streaming | Kafka | 600M events/day |
| Stream Processing | Flink | Spam detection, counter updates |
| Batch Analytics | Spark GraphX | PageRank, communities (weekly) |
| Analytics Store | ClickHouse | Historical follow metrics |
| Fan-out | Custom service | Hybrid push/pull, < 5s delivery |
| Suggestions | ML + Graph | 50 candidates/user, 24h refresh |

