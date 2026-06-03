# Neo4j - Real World Use Cases & Production Guide

## Core Concepts

### Property Graph Model

```
┌─────────────────────┐          ┌─────────────────────┐
│  NODE               │          │  NODE               │
│  Labels: [:Person]  │          │  Labels: [:Company] │
│                     │          │                     │
│  Properties:        │  :WORKS_AT (since: 2020)      │
│    name: "Alice"    │─────────────────────────────►  │
│    age: 32          │          │  Properties:        │
│    city: "NYC"      │          │    name: "Acme"     │
└─────────────────────┘          │    revenue: 5M      │
        │                        └─────────────────────┘
        │ :KNOWS (since: 2018)
        ▼
┌─────────────────────┐
│  NODE               │
│  Labels: [:Person]  │
│  Properties:        │
│    name: "Bob"      │
└─────────────────────┘
```

**Four building blocks:**
- **Nodes** - Entities (circles in visualization)
- **Relationships** - Always directed, always have a type, connect exactly two nodes
- **Properties** - Key-value pairs on both nodes and relationships
- **Labels** - Categorize nodes (like types/tags)

### Index-Free Adjacency

The defining characteristic that makes Neo4j fast for graph traversals:

```
Traditional RDBMS (Join Tables):
┌──────────┐     ┌──────────────────┐     ┌──────────┐
│ Person   │     │ person_friends   │     │ Person   │
│ id: 1    │◄────│ person_id: 1     │────►│ id: 2    │
│ name: A  │     │ friend_id: 2     │     │ name: B  │
└──────────┘     └──────────────────┘     └──────────┘
                 Global Index Lookup O(log n) per hop

Neo4j (Direct Pointers):
┌──────────┐                    ┌──────────┐
│ Person   │   Physical Pointer │ Person   │
│ id: 1    │───────────────────►│ id: 2    │
│ name: A  │   O(1) traversal  │ name: B  │
│          │                    │          │
│ rel_ptr ─┼───► [KNOWS]───────┼─► node_ptr│
└──────────┘                    └──────────┘
```

**Key insight:** Each node physically stores pointers to its adjacent nodes. Traversal cost is proportional to the subgraph explored, NOT the total graph size.

| Operation              | RDBMS              | Neo4j          |
|------------------------|--------------------|----------------|
| 1-hop traversal        | O(log n) join      | O(1) pointer   |
| k-hop traversal        | O(n^k) joins       | O(m) where m = edges traversed |
| Friend-of-friend (depth 5) | Minutes/Timeout | Milliseconds   |

### Cypher Query Language

```cypher
// CREATE - Insert data
CREATE (alice:Person {name: 'Alice', age: 32})
CREATE (bob:Person {name: 'Bob', age: 28})
CREATE (alice)-[:KNOWS {since: 2018}]->(bob)

// MATCH - Pattern matching (read)
MATCH (p:Person)-[:KNOWS]->(friend)
WHERE p.name = 'Alice'
RETURN friend.name, friend.age

// MERGE - Idempotent upsert (create if not exists)
MERGE (c:Company {name: 'Acme'})
ON CREATE SET c.founded = 2010
ON MATCH SET c.lastSeen = datetime()

// Variable-length paths
MATCH path = (a:Person)-[:KNOWS*1..3]->(b:Person)
WHERE a.name = 'Alice'
RETURN path

// Aggregation
MATCH (p:Person)-[:PURCHASED]->(product:Product)
RETURN product.category, count(p) AS buyers
ORDER BY buyers DESC
LIMIT 10

// OPTIONAL MATCH (left outer join equivalent)
MATCH (p:Person)
OPTIONAL MATCH (p)-[:WORKS_AT]->(c:Company)
RETURN p.name, c.name AS company

// WITH (pipeline/subquery)
MATCH (p:Person)-[:KNOWS]->(friend)
WITH p, count(friend) AS friendCount
WHERE friendCount > 5
RETURN p.name, friendCount
```

### Graph Algorithms

```cypher
// PageRank - Find influential nodes
CALL gds.pageRank.stream('myGraph')
YIELD nodeId, score
RETURN gds.util.asNode(nodeId).name AS name, score
ORDER BY score DESC LIMIT 10

// Shortest Path - Dijkstra
MATCH (source:City {name: 'NYC'}), (target:City {name: 'LA'})
CALL gds.shortestPath.dijkstra.stream('roadNetwork', {
    sourceNode: source,
    targetNode: target,
    relationshipWeightProperty: 'distance'
})
YIELD path, totalCost
RETURN path, totalCost

// Community Detection - Louvain
CALL gds.louvain.stream('socialGraph')
YIELD nodeId, communityId
RETURN communityId, collect(gds.util.asNode(nodeId).name) AS members
ORDER BY size(members) DESC

// Betweenness Centrality - Bridge nodes
CALL gds.betweenness.stream('myGraph')
YIELD nodeId, score
RETURN gds.util.asNode(nodeId).name, score
ORDER BY score DESC
```

### ACID Transactions

```cypher
// Neo4j is fully ACID compliant
// Every Cypher query runs in a transaction

// Explicit transaction (in application code):
// session.beginTransaction()
// tx.run("MATCH ...")
// tx.run("CREATE ...")
// tx.commit()  -- atomic: all or nothing

// Write locks on nodes/relationships being modified
// Read committed isolation level by default
// Deadlock detection with automatic retry
```

---

## 5 Real-World Use Cases

---

### 1. LinkedIn "People You May Know"

**Problem:** Recommend connections based on mutual friends (2nd/3rd degree connections).

**Why Graph DB over Relational:**
- RDBMS: Finding 3rd degree connections requires 3 self-joins on a billion-row table = catastrophic performance
- Neo4j: Traversal from a single user through 3 hops = milliseconds regardless of total user count

**Graph Model:**
```
(:Person)─[:CONNECTED_TO]─►(:Person)
    │                           │
    ├──[:WORKS_AT]──►(:Company) │
    ├──[:STUDIED_AT]►(:School)  │
    └──[:HAS_SKILL]─►(:Skill)◄─┘

   (Alice)──CONNECTED_TO──►(Bob)──CONNECTED_TO──►(Charlie)
     │                       │                       │
     └───WORKS_AT──►(Google)◄──WORKS_AT──────────────┘
```

**Cypher Queries:**

```cypher
// 2nd degree connections (friends of friends) not already connected
MATCH (me:Person {id: $userId})-[:CONNECTED_TO*2]-(suggestion:Person)
WHERE NOT (me)-[:CONNECTED_TO]-(suggestion)
  AND me <> suggestion
WITH suggestion, count(*) AS mutualFriends
ORDER BY mutualFriends DESC
LIMIT 20
RETURN suggestion.name, mutualFriends

// Enhanced scoring: shared companies, schools, skills
MATCH (me:Person {id: $userId})
MATCH (me)-[:CONNECTED_TO*2..3]-(candidate:Person)
WHERE NOT (me)-[:CONNECTED_TO]-(candidate) AND me <> candidate
WITH me, candidate, count{(me)-[:CONNECTED_TO*2]-(candidate)} AS mutual2
OPTIONAL MATCH (me)-[:WORKS_AT]->(c:Company)<-[:WORKS_AT]-(candidate)
OPTIONAL MATCH (me)-[:STUDIED_AT]->(s:School)<-[:STUDIED_AT]-(candidate)
WITH candidate, mutual2,
     count(c) AS sharedCompanies,
     count(s) AS sharedSchools
WITH candidate,
     mutual2 * 3 + sharedCompanies * 5 + sharedSchools * 4 AS score
ORDER BY score DESC
LIMIT 10
RETURN candidate.name, score
```

**Performance:**
- 500M+ users, billions of connections
- 2nd degree: ~2ms, 3rd degree: ~20ms
- RDBMS equivalent: 30+ seconds or timeout at this scale

---

### 2. NASA Knowledge Graph (Lessons Learned)

**Problem:** NASA's Lessons Learned database captures knowledge from missions, failures, and successes. Engineers need to find relevant lessons across decades of unstructured documents.

**Why Graph DB over Relational:**
- Knowledge is interconnected: a lesson links to missions, systems, failure modes, personnel, technologies
- Relational model requires dozens of junction tables; graph naturally represents knowledge connections
- Discovery queries ("what lessons relate to thermal protection across all shuttle missions?") require unknown-depth traversals

**Graph Model:**
```
(:Lesson)─[:APPLIES_TO]──►(:Mission)
    │                          │
    ├──[:INVOLVES_SYSTEM]──►(:System)──[:SUBSYSTEM_OF]──►(:System)
    │                          │
    ├──[:CAUSED_BY]────────►(:FailureMode)
    │                          │
    ├──[:AUTHORED_BY]──────►(:Engineer)──[:WORKED_ON]──►(:Mission)
    │
    └──[:TAGGED]───────────►(:Topic)──[:RELATED_TO]──►(:Topic)

  (Lesson-2003-001)──APPLIES_TO──►(STS-107 Columbia)
        │                               │
        ├──INVOLVES_SYSTEM──►(TPS)──────►SUBSYSTEM_OF──►(Orbiter)
        │
        └──CAUSED_BY──►(Foam_Shedding)──RELATED_TO──►(Debris_Impact)
```

**Cypher Queries:**

```cypher
// Find all lessons related to thermal protection across missions
MATCH (l:Lesson)-[:INVOLVES_SYSTEM]->(s:System)
WHERE s.name CONTAINS 'Thermal' OR s.name CONTAINS 'TPS'
MATCH (l)-[:APPLIES_TO]->(m:Mission)
RETURN l.title, l.summary, m.name, l.severity
ORDER BY l.severity DESC

// Knowledge path: how two failure modes are connected
MATCH path = shortestPath(
  (f1:FailureMode {name: 'Foam Shedding'})-[*..6]-
  (f2:FailureMode {name: 'O-Ring Erosion'})
)
RETURN path

// Lessons by engineer expertise graph
MATCH (e:Engineer)-[:AUTHORED]->(l:Lesson)-[:INVOLVES_SYSTEM]->(s:System)
WITH e, s, count(l) AS expertise
WHERE expertise > 3
RETURN e.name, s.name, expertise
ORDER BY expertise DESC
```

**Performance:**
- 50K+ lessons, millions of connections across 60+ years of spaceflight
- Concept traversal (find related lessons through topic chains): <50ms
- Full-text + graph hybrid queries for semantic search

---

### 3. eBay Catalog Graph

**Problem:** Model 1.5B+ product listings with complex category hierarchies, compatibility relationships, and recommendation paths.

**Why Graph DB over Relational:**
- Product compatibility ("fits with") creates dense relationship networks
- Category hierarchies are arbitrary depth (tree traversal)
- "Customers also bought" requires multi-hop traversal through purchase history
- Relational: recursive CTEs or materialized paths = slow, inflexible

**Graph Model:**
```
(:Product)─[:IN_CATEGORY]──►(:Category)──[:SUBCATEGORY_OF]──►(:Category)
    │                                                              │
    ├──[:COMPATIBLE_WITH]──►(:Product)                             │
    │                                                              │
    ├──[:SOLD_BY]──────────►(:Seller)                              │
    │                                                              │
    ├──[:PURCHASED_BY]─────►(:Buyer)──[:PURCHASED]──►(:Product)    │
    │                                                              │
    └──[:HAS_SPEC]─────────►(:Specification {key, value})          │

  (iPhone15Case)──COMPATIBLE_WITH──►(iPhone15)
       │                               │
       ├──IN_CATEGORY──►(Cases)────────►SUBCATEGORY_OF──►(Accessories)
       │                                                      │
       └──ALSO_BOUGHT──►(ScreenProtector)                     ▼
                              │                         (Electronics)
                              └──IN_CATEGORY──►(Protection)
```

**Cypher Queries:**

```cypher
// Product recommendations through purchase patterns
MATCH (p:Product {id: $productId})<-[:PURCHASED]-(buyer:Buyer)-[:PURCHASED]->(other:Product)
WHERE other <> p
WITH other, count(DISTINCT buyer) AS coBuyers
ORDER BY coBuyers DESC
LIMIT 10
RETURN other.title, other.price, coBuyers

// Full category path (arbitrary depth)
MATCH path = (p:Product {id: $productId})-[:IN_CATEGORY]->(:Category)-[:SUBCATEGORY_OF*0..10]->(root:Category)
WHERE NOT (root)-[:SUBCATEGORY_OF]->()
RETURN [node IN nodes(path) | node.name] AS breadcrumb

// Compatible products across categories
MATCH (p:Product {id: $productId})-[:COMPATIBLE_WITH*1..2]-(compatible:Product)
MATCH (compatible)-[:IN_CATEGORY]->(cat:Category)
RETURN cat.name, collect(compatible.title)[..5] AS products
```

**Performance:**
- 1.5B listings, billions of relationships
- Compatibility traversal: <5ms
- Recommendation (2-hop through buyers): ~15ms
- Category tree traversal: <2ms

---

### 4. Walmart Supply Chain Optimization

**Problem:** Optimize routing across 11,000+ stores, 150+ distribution centers, thousands of suppliers, and millions of products with real-time demand signals.

**Why Graph DB over Relational:**
- Supply chain is inherently a network/graph problem
- Route optimization requires shortest-path algorithms native to graph DBs
- Multi-modal constraints (truck capacity, time windows, perishability) modeled as relationship properties
- RDBMS: complex stored procedures with iterative algorithms; Graph: native algorithm library

**Graph Model:**
```
(:Supplier)─[:SUPPLIES]──►(:Product)──[:STOCKED_AT]──►(:Store)
                              │                          │
(:DC)──[:ROUTES_TO]──►(:DC)──┼──[:SERVES]──────────────►│
  │                           │                          │
  └──[:DISTANCE {miles, time, cost}]──►(:Store)          │
                                                         │
(:Store)──[:NEARBY {distance}]──►(:Store)                │
    │                                                    │
    └──[:DEMAND {product, quantity, date}]────────────────┘

  (Supplier_A)──SUPPLIES──►(Widget_X)
       │                       │
       └──SHIPS_TO──►(DC_Dallas)──ROUTES_TO──►(DC_Memphis)
                         │                        │
                         ├──SERVES──►(Store_101)  └──SERVES──►(Store_205)
                         │     distance: 45mi          distance: 30mi
                         │     cost: $120              cost: $85
                         └──SERVES──►(Store_102)
```

**Cypher Queries:**

```cypher
// Optimal distribution path from supplier to store
MATCH (supplier:Supplier {name: 'SupplierA'}),
      (store:Store {id: 'Store_101'})
CALL gds.shortestPath.dijkstra.stream('supplyNetwork', {
    sourceNode: supplier,
    targetNode: store,
    relationshipWeightProperty: 'cost'
})
YIELD path, totalCost
RETURN [n IN nodes(path) | n.name] AS route, totalCost

// Identify bottleneck DCs (high betweenness centrality)
CALL gds.betweenness.stream('supplyNetwork', {
    nodeLabels: ['DC'],
    relationshipTypes: ['ROUTES_TO']
})
YIELD nodeId, score
RETURN gds.util.asNode(nodeId).name AS dc, score
ORDER BY score DESC LIMIT 5

// Demand-aware restocking: find understocked stores within DC range
MATCH (dc:DC {name: 'DC_Dallas'})-[r:SERVES]->(store:Store)
WHERE r.distance < 100
MATCH (store)-[d:DEMAND]->(p:Product)
WHERE d.quantity > store.currentStock
RETURN store.id, p.name, d.quantity - store.currentStock AS deficit
ORDER BY deficit DESC
```

**Performance:**
- 11K stores + 150 DCs + 100K suppliers = millions of route combinations
- Shortest path (single source): <10ms
- Full network optimization (batch): seconds vs hours in traditional systems
- Real-time rerouting on disruption: <100ms

---

### 5. Panama Papers (ICIJ Investigation)

**Problem:** Investigate 11.5M leaked documents revealing hidden financial networks, shell companies, and offshore tax evasion across 200+ countries.

**Why Graph DB over Relational:**
- Financial fraud hides in relationship patterns, not individual records
- Shell company chains: Company A owns B owns C owns D... arbitrary depth
- RDBMS: impossible to query "find circular ownership" or "degrees of separation to a politician"
- Graph: pattern matching on network topology is native

**Graph Model:**
```
(:Person)─[:OFFICER_OF]────►(:Entity)──[:REGISTERED_IN]──►(:Jurisdiction)
    │                           │
    │                    [:CONNECTED_TO]
    │                           │
    ├──[:SHAREHOLDER_OF]───►(:Entity)──[:INTERMEDIARY]──►(:Intermediary)
    │                           │
    └──[:SAME_ADDRESS_AS]──►(:Address)◄──[:REGISTERED_AT]──┘

  (Politician_X)──OFFICER_OF──►(ShellCo_BVI_1)
       │                            │
       │                     CONNECTED_TO
       │                            ▼
       └──SHAREHOLDER_OF──►(ShellCo_Panama_2)──REGISTERED_IN──►(Panama)
                                    │
                             CONNECTED_TO
                                    ▼
                           (ShellCo_Seychelles_3)──INTERMEDIARY──►(MossFon)
```

**Cypher Queries:**

```cypher
// Find all entities connected to a person within 4 hops
MATCH path = (p:Person {name: 'Person X'})-[*1..4]-(e:Entity)
RETURN path

// Circular ownership detection (fraud pattern)
MATCH cycle = (e:Entity)-[:CONNECTED_TO*3..8]->(e)
RETURN cycle, length(cycle) AS chainLength
ORDER BY chainLength DESC
LIMIT 20

// Politically Exposed Persons (PEPs) connected to offshore entities
MATCH (pep:Person)-[:OFFICER_OF|SHAREHOLDER_OF*1..3]->(entity:Entity)
WHERE pep.isPEP = true
MATCH (entity)-[:REGISTERED_IN]->(j:Jurisdiction)
WHERE j.name IN ['British Virgin Islands', 'Panama', 'Seychelles']
RETURN pep.name, pep.country, collect(DISTINCT entity.name) AS shells,
       collect(DISTINCT j.name) AS jurisdictions

// Shared address pattern (multiple entities at same address = red flag)
MATCH (a:Address)<-[:REGISTERED_AT]-(e:Entity)
WITH a, collect(e) AS entities, count(e) AS entityCount
WHERE entityCount > 50
RETURN a.address, entityCount
ORDER BY entityCount DESC
```

**Performance:**
- 11.5M documents → 800K+ entities, 2M+ relationships
- Pattern detection across full graph: seconds
- Path finding between any two entities: <50ms
- Circular ownership (cycle detection): <500ms for entire graph
- RDBMS equivalent queries: hours or impossible to express in SQL

---

## Replication: Causal Clustering

### Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │            CAUSAL CLUSTER                    │
                    │                                             │
                    │  ┌────────┐  ┌────────┐  ┌────────┐       │
                    │  │ CORE 1 │◄─┤ CORE 2 │◄─┤ CORE 3 │       │
                    │  │(Leader)│──►│        │──►│        │       │
                    │  └───┬────┘  └────┬───┘  └────┬───┘       │
                    │      │ Raft       │ Raft      │ Raft       │
                    │      │ Consensus  │           │            │
                    │      ▼            ▼           ▼            │
                    │  ┌──────────────────────────────────┐      │
                    │  │     Transaction Log (Raft Log)    │      │
                    │  └──────────────────────────────────┘      │
                    │      │            │           │            │
                    └──────┼────────────┼───────────┼────────────┘
                           │            │           │
              Async pull   │            │           │
                    ┌──────▼──┐   ┌─────▼───┐  ┌───▼─────┐
                    │ READ    │   │ READ    │  │ READ    │
                    │REPLICA 1│   │REPLICA 2│  │REPLICA 3│
                    └─────────┘   └─────────┘  └─────────┘
```

### Raft Consensus (Core Servers)

```
Election:                    Normal Operation:
                             
 CORE1: "I'm candidate"     Leader ──► Follower1: AppendEntries(tx)
   │                                │                    │
   ├──► CORE2: "Vote for me"       │                    ├── ACK
   │       └── "Yes" ──────►       │                    │
   ├──► CORE3: "Vote for me"       ├──► Follower2: AppendEntries(tx)
   │       └── "Yes" ──────►       │                    │
   │                                │                    ├── ACK
   ▼                                ▼                    │
 CORE1 becomes LEADER        Majority ACK = COMMITTED   ▼
                                                     Client: "Success"
```

- **Write quorum:** Majority of cores must acknowledge (2 of 3, 3 of 5)
- **Leader election:** Automatic on leader failure (~seconds)
- **Minimum cores:** 3 (tolerates 1 failure), 5 (tolerates 2)

### Bookmark-Based Causal Consistency

```
Client                Core (Leader)           Read Replica
  │                        │                       │
  │── WRITE tx ──────────►│                       │
  │                        │── replicate ────────►│
  │◄── bookmark:abc123 ───│                       │
  │                        │                       │
  │── READ (bookmark:abc123) ────────────────────►│
  │                        │                       │
  │                        │     (waits until      │
  │                        │      abc123 applied)  │
  │◄────────────────────── result ────────────────│
```

- Bookmarks ensure "read your own writes" consistency
- Client passes bookmark from write response to subsequent reads
- Read replica waits until it has caught up to that bookmark before responding

### Multi-Data Center Pattern

```
          DC-EAST (Primary)              DC-WEST (Secondary)
     ┌─────────────────────┐        ┌─────────────────────┐
     │  Core1  Core2  Core3│        │  Core4  Core5  Core6│
     │    ▲      ▲      ▲  │        │    ▲      ▲      ▲  │
     │    └──Raft─┴──Raft┘  │◄──────►│    └──Raft─┴──Raft┘  │
     │                      │  WAN   │                      │
     │  RR1  RR2  RR3      │        │  RR4  RR5  RR6      │
     └─────────────────────┘        └─────────────────────┘

     Minimum: 3 cores per DC (or 2+1 for witness)
     Writes: Route to leader (any DC)
     Reads: Local read replicas preferred
```

Configuration:
```properties
# neo4j.conf for multi-DC
server.cluster.system_database_mode=PRIMARY  # or SECONDARY
server.groups=dc-east
server.cluster.raft.leader_transfer.priority_group=dc-east
```

---

## Scalability

### Neo4j Fabric (Sharding / Federated Queries)

```
                    ┌──────────────────────┐
                    │   FABRIC PROXY       │
                    │   (Query Router)     │
                    └──────┬───────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
     ┌────────────┐ ┌────────────┐ ┌────────────┐
     │ Shard 1    │ │ Shard 2    │ │ Shard 3    │
     │ Users A-F  │ │ Users G-N  │ │ Users O-Z  │
     │ (Cluster)  │ │ (Cluster)  │ │ (Cluster)  │
     └────────────┘ └────────────┘ └────────────┘
```

```cypher
// Fabric query spanning multiple databases
USE fabric.allShards
MATCH (u:User)-[:PURCHASED]->(p:Product)
RETURN u.name, count(p) AS purchases
ORDER BY purchases DESC LIMIT 10

// Route to specific shard
USE fabric.shard1
MATCH (u:User {name: 'Alice'}) RETURN u
```

### Read Replicas for Scale

```
Writes ──► Leader Core (single writer)
                │
                ├── async replication ──► Read Replica 1 ──► Reads (pool)
                ├── async replication ──► Read Replica 2 ──► Reads (pool)
                └── async replication ──► Read Replica N ──► Reads (pool)
```

- Scale reads horizontally by adding read replicas
- Eventually consistent (milliseconds lag typically)
- Use bookmarks for causal consistency when needed

### Graph Partitioning Challenges

```
The "hairball" problem - graphs are notoriously hard to partition:

  Shard A          │        Shard B
                   │
    (Alice)────────┼──────►(Bob)         ← Cross-shard edge!
      │            │         │
      ▼            │         ▼
    (Carol)        │       (Dave)
      │            │         │
      └────────────┼─────────┘           ← Another cross-shard edge!
                   │

Problems:
- Social graphs: power-law distribution, no clean cuts
- Cross-shard traversals require network hops
- Multi-shard transactions need 2PC (slow)
```

**Strategies:**
1. **Domain-based sharding** - Shard by geography, time, or entity type
2. **Replicate hot nodes** - Keep highly-connected nodes on all shards
3. **Fabric federation** - Query across shards with Fabric proxy
4. **Avoid sharding** - Neo4j single instance handles 34B+ nodes; scale reads with replicas

### APOC Procedures (Awesome Procedures on Cypher)

```cypher
// Batch processing (avoid OOM on large operations)
CALL apoc.periodic.iterate(
  "MATCH (n:OldLabel) RETURN n",
  "SET n:NewLabel REMOVE n:OldLabel",
  {batchSize: 10000, parallel: true}
)

// Load JSON from API
CALL apoc.load.json('https://api.example.com/data') YIELD value
CREATE (n:Item) SET n = value

// Export subgraph
CALL apoc.export.cypher.query(
  "MATCH (n:Person)-[r]->(m) RETURN *",
  "/tmp/export.cypher", {}
)

// Graph refactoring
CALL apoc.refactor.mergeNodes([node1, node2], {properties: 'combine'})

// TTL (auto-delete expired nodes)
CALL apoc.ttl.expire(node, 3600, 's')
```

### Graph Data Science (GDS) Library

```cypher
// Project in-memory graph for algorithms
CALL gds.graph.project('social', 'Person', 'KNOWS')

// Node similarity (for recommendations)
CALL gds.nodeSimilarity.stream('social')
YIELD node1, node2, similarity
RETURN gds.util.asNode(node1).name AS person1,
       gds.util.asNode(node2).name AS person2,
       similarity
ORDER BY similarity DESC

// Community detection (Louvain)
CALL gds.louvain.write('social', {writeProperty: 'community'})

// Node embedding (for ML pipelines)
CALL gds.node2vec.stream('social', {embeddingDimension: 64})
YIELD nodeId, embedding
RETURN gds.util.asNode(nodeId).name, embedding

// Link prediction pipeline
CALL gds.beta.pipeline.linkPrediction.create('myPipeline')
CALL gds.beta.pipeline.linkPrediction.addFeature('myPipeline', 'cosine', {
  nodeProperties: ['embedding']
})
```

---

## Production Setup

### JVM Tuning

```properties
# neo4j.conf

# Heap (for Cypher execution, transaction state)
server.memory.heap.initial_size=8g
server.memory.heap.max_size=8g
# Rule: Set initial = max to avoid GC pauses from resizing

# Page Cache (for graph store - nodes, relationships, properties)
server.memory.pagecache.size=16g
# Rule: Enough to fit entire graph store in memory
# Check: CALL dbms.queryJmx('org.neo4j:*,name=Page cache')
# Target: >99% hit ratio

# Transaction Memory
db.memory.transaction.total.max=4g
db.memory.transaction.max=1g

# GC Settings (in neo4j-wrapper.conf or JAVA_OPTS)
# Use G1GC (default in Neo4j 5+)
-XX:+UseG1GC
-XX:MaxGCPauseMillis=100
-XX:-OmitStackTraceInFastThrow
-XX:+AlwaysPreTouch

# Memory formula:
# Total RAM = Heap + Page Cache + OS (2-4GB) + GDS projection (if used)
# Example 32GB machine: 8GB heap + 16GB page cache + 4GB OS + 4GB GDS
```

### Transaction Logs & Backup

```properties
# Transaction log retention
db.tx_log.rotation.retention_policy=2 days
db.tx_log.rotation.size=256m

# Checkpoint frequency
db.checkpoint.interval.time=15m
db.checkpoint.interval.tx=100000
```

```bash
# Online backup (Enterprise)
neo4j-admin database backup neo4j --to-path=/backups/$(date +%Y%m%d)

# Offline backup (Community)
neo4j stop
neo4j-admin database dump neo4j --to-path=/backups/neo4j.dump
neo4j start

# Restore
neo4j-admin database restore --from-path=/backups/20240101 neo4j

# Consistency check
neo4j-admin database check neo4j
```

### Index Management

```cypher
// B-Tree index (range queries)
CREATE INDEX person_name FOR (n:Person) ON (n.name)

// Composite index
CREATE INDEX person_name_age FOR (n:Person) ON (n.name, n.age)

// Full-text index (Lucene-backed)
CREATE FULLTEXT INDEX productSearch FOR (n:Product) ON EACH [n.title, n.description]

// Usage:
CALL db.index.fulltext.queryNodes('productSearch', 'wireless headphones~')
YIELD node, score
RETURN node.title, score

// Relationship index
CREATE INDEX knows_since FOR ()-[r:KNOWS]-() ON (r.since)

// Existence constraint (schema enforcement)
CREATE CONSTRAINT person_has_name FOR (p:Person) REQUIRE p.name IS NOT NULL

// Uniqueness constraint (also creates index)
CREATE CONSTRAINT person_email_unique FOR (p:Person) REQUIRE p.email IS UNIQUE

// Node key (composite uniqueness)
CREATE CONSTRAINT product_key FOR (p:Product) REQUIRE (p.sku, p.region) IS NODE KEY

// List all indexes
SHOW INDEXES

// Drop
DROP INDEX person_name
```

### Monitoring

```cypher
// Active queries
CALL dbms.listQueries() YIELD queryId, query, elapsedTimeMillis
WHERE elapsedTimeMillis > 5000
RETURN queryId, query, elapsedTimeMillis

// Kill slow query
CALL dbms.killQuery('query-123')

// Database metrics
:sysinfo  // in Neo4j Browser

// Key metrics to monitor:
// - Page cache hit ratio (target >98%)
// - Bolt connections active
// - Transaction commit/rollback rate
// - Heap usage / GC pauses
// - Cluster: replication lag, leader elections
```

```yaml
# Prometheus endpoint (neo4j.conf)
server.metrics.prometheus.enabled=true
server.metrics.prometheus.endpoint=0.0.0.0:2004

# Key Prometheus metrics:
# neo4j_page_cache_hit_ratio
# neo4j_bolt_connections_running
# neo4j_transaction_committed_total
# neo4j_transaction_rollbacks_total
# neo4j_database_store_size_total
# neo4j_cluster_raft_replication_lag
```

```
Grafana Dashboard Layout:
┌──────────────────┬──────────────────┬──────────────────┐
│ Page Cache Hit % │ Active Queries   │ Heap Used/Max    │
│     99.2%        │      47          │   6.2/8 GB       │
├──────────────────┼──────────────────┼──────────────────┤
│ Tx/sec (commit)  │ Bolt Connections │ Store Size       │
│     1,240        │      312         │   48 GB          │
├──────────────────┼──────────────────┼──────────────────┤
│ GC Pause (p99)   │ Replication Lag  │ Cluster Status   │
│     12ms         │      50ms        │   3C + 5RR ✓     │
└──────────────────┴──────────────────┴──────────────────┘
```

---

## Traversal Performance Summary

| Scenario | Depth | Relationships | Neo4j Time | RDBMS Time |
|----------|-------|---------------|------------|------------|
| Friend lookup | 1 | 100s | <1ms | ~2ms |
| Friend-of-friend | 2 | 10K | ~2ms | ~200ms |
| 3rd degree | 3 | 1M | ~20ms | 30+ sec |
| 4th degree | 4 | 10M+ | ~200ms | Timeout |
| Shortest path (large graph) | variable | 1B+ edges | ~50ms | Impossible |
| Pattern match (fraud ring) | 3-8 | millions | <500ms | Hours |

**Why:** Index-free adjacency means each hop is O(1) pointer dereference, not O(log n) index scan. Performance depends on subgraph size explored, not total data size.
