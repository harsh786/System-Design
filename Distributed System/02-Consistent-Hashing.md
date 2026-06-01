# Consistent Hashing

## Table of Contents
1. [Problem Statement](#1-problem-statement)
2. [Core Concept](#2-core-concept)
3. [Virtual Nodes](#3-virtual-nodes-vnodes)
4. [Algorithm Deep Dive](#4-algorithm-deep-dive)
5. [Node Addition/Removal](#5-node-additionremoval)
6. [Weighted Consistent Hashing](#6-weighted-consistent-hashing)
7. [Jump Consistent Hashing](#7-jump-consistent-hashing)
8. [Real-World Implementations](#8-real-world-implementations)
9. [Replication with Consistent Hashing](#9-replication-with-consistent-hashing)
10. [Failure Handling](#10-failure-handling)
11. [Architect's Guide](#11-architects-guide)

---

## 1. Problem Statement

### Why Naive Modulo Hashing Fails Catastrophically

In a distributed system with `N` nodes, the simplest key-to-node mapping is:

```
node = hash(key) % N
```

This works perfectly with a **fixed** number of nodes. The moment you add or remove a node, catastrophe strikes.

### The Math of Redistribution

Consider 4 nodes and 12 keys with hash values 0-11:

```
N = 4 nodes

Key:    k0  k1  k2  k3  k4  k5  k6  k7  k8  k9  k10  k11
Hash:    0   1   2   3   4   5   6   7   8   9   10   11
Node:    0   1   2   3   0   1   2   3   0   1    2    3
         (hash % 4)
```

Now add 1 node (N = 4 -> 5):

```
N = 5 nodes

Key:    k0  k1  k2  k3  k4  k5  k6  k7  k8  k9  k10  k11
Hash:    0   1   2   3   4   5   6   7   8   9   10   11
Node:    0   1   2   3   4   0   1   2   3   4    0    1
         (hash % 5)
```

**Keys that moved:** k4, k5, k6, k7, k8, k9, k10, k11 = **8 out of 12 keys (67%)**

### General Formula for Key Displacement

When going from `N` to `N+1` nodes:

```
Fraction of keys that must move ≈ (N) / (N+1)

N=4  -> N=5:   4/5  = 80% expected displacement
N=10 -> N=11:  10/11 = 91% expected displacement
N=100-> N=101: 100/101 = 99% expected displacement
```

As cluster size grows, **nearly ALL keys must be remapped** when a single node changes. This causes:

1. **Cache stampede** - Millions of cache misses simultaneously hit the backend
2. **Data migration storms** - Massive network I/O to reshuffle data
3. **Cascading failures** - Overloaded backends trigger timeouts, causing more failures
4. **Extended unavailability** - System is inconsistent during the migration window

### What We Need

A hashing scheme where adding/removing a node only requires remapping **K/N** keys (where K = total keys, N = total nodes). This is the theoretical minimum - you cannot do better because the new node must receive *some* keys to be useful.

---

## 2. Core Concept

### The Hash Ring

Consistent hashing maps both **nodes** and **keys** onto the same circular hash space (typically `[0, 2^32 - 1]` or `[0, 2^128 - 1]`). The circle wraps around: position `2^32 - 1` is adjacent to position `0`.

```
                        Hash Space: [0, 2^32)

                             0 / 2^32
                              |
                     N3 ------+------ K1
                   /                       \
                 /                           \
               K5                             N1
              |                                 |
              |                                 |
    3/4 * 2^32 ----         RING          ---- 1/4 * 2^32
              |                                 |
              |                                 |
               K4                             K2
                 \                           /
                   \                       /
                     N2 ------+------ K3
                              |
                         1/2 * 2^32
```

### How It Works

1. **Hash each node** (e.g., by IP or hostname) to get its position on the ring
2. **Hash each key** to get its position on the ring
3. **Walk clockwise** from the key's position until you hit the first node - that node owns the key

### Key Assignment Example

```
Ring positions (simplified to 0-99 for clarity):

Nodes:   N1=15,  N2=45,  N3=78

Keys:    K1=5,   K2=20,  K3=42,  K4=50,  K5=80,  K6=95


         0          15         30         45         60         78      99
    ─────┼───────────┼──────────┼──────────┼──────────┼──────────┼───────┼──
         ↑     ↑              ↑  ↑              ↑              ↑  ↑
         K6    K1             K2 K3             K4             K5 (wrap)


  Key Assignments (walk clockwise to next node):
  ┌──────┬──────────┬─────────────────────────────────────┐
  │ Key  │ Position │ Assigned To (next clockwise node)    │
  ├──────┼──────────┼─────────────────────────────────────┤
  │ K1   │    5     │ N1 (at 15)                          │
  │ K2   │   20     │ N2 (at 45)                          │
  │ K3   │   42     │ N2 (at 45)                          │
  │ K4   │   50     │ N3 (at 78)                          │
  │ K5   │   80     │ N1 (at 15) ← wraps around!         │
  │ K6   │   95     │ N1 (at 15) ← wraps around!         │
  └──────┴──────────┴─────────────────────────────────────┘

  Load: N1 owns 3 keys, N2 owns 2 keys, N3 owns 1 key
```

### Why This Is Better

When a node is added or removed, only the keys in the **arc** between the affected node and its predecessor are remapped. All other keys remain where they are.

---

## 3. Virtual Nodes (VNodes)

### The Problem with Physical Nodes Only

With only a few physical nodes, hash functions cannot guarantee uniform distribution around the ring. Some nodes will own much larger arcs than others.

```
  UNBALANCED (3 physical nodes, no vnodes):

              0
              |
              N1 (pos: 5)
             /|
            / |
           /  |                N1 owns arc: 80 → 5  = 25% of ring
          /   |                N2 owns arc:  5 → 10 =  5% of ring  ← STARVING
         /    N2 (pos: 10)     N3 owns arc: 10 → 80 = 70% of ring ← OVERLOADED
        |     |
        |     |
        |     |
        |     |
        |     |
         \    |
          \   |
           \  |
            \ |
             \|
              N3 (pos: 80)
              |
```

With random hash placement and `N` nodes, the expected load on the most loaded node is `O(log N / N)` instead of the ideal `1/N`. For 3 nodes, one node could handle 70%+ of traffic.

### Solution: Virtual Nodes

Map each physical node to **multiple positions** (virtual nodes) on the ring. If each physical node has `V` virtual nodes, we have `N * V` total positions on the ring.

```
  BALANCED (3 physical nodes, 4 vnodes each = 12 ring positions):

              0
              |
         N1_a ── N3_c
        /              \
       /                \
     N2_b              N1_d        Legend:
      |                  |          N1: positions a, b, c, d (roughly every 90°)
      |                  |          N2: positions a, b, c, d (interleaved)
      |     RING         |          N3: positions a, b, c, d (interleaved)
      |                  |
     N3_a              N2_c        Each physical node "owns" ~33% of the ring
      |                  |          because its vnodes are spread uniformly
       \                /
        \              /
         N1_c ── N2_d
              |
```

### Statistical Improvement

With `V` virtual nodes per physical node:

| Virtual Nodes (V) | Max Load / Avg Load | Std Dev of Load |
|--------------------|---------------------|-----------------|
| 1                  | ~5.0x               | High            |
| 10                 | ~2.0x               | Moderate        |
| 50                 | ~1.3x               | Low             |
| 100                | ~1.15x              | Very Low        |
| 150                | ~1.10x              | Minimal         |
| 256                | ~1.07x              | Near-ideal      |
| 500                | ~1.05x              | Negligible      |

### Cassandra's Approach

Apache Cassandra uses **256 vnodes** per physical node (configurable via `num_tokens` in `cassandra.yaml`):

```yaml
# cassandra.yaml
num_tokens: 256     # Each node gets 256 random positions on the token ring
```

**Why 256?**
- Provides <10% load imbalance across nodes
- Allows fine-grained data streaming during node addition (256 small ranges vs 1 large range)
- Each vnode token range is small enough that streaming during repair is fast
- Trade-off: More vnodes = more metadata overhead in gossip protocol

### Memory/Metadata Trade-off

```
Ring metadata size = N_physical * V * (token_size + node_info)

Example:
  100 physical nodes * 256 vnodes * (8 bytes token + 16 bytes node_id)
  = 100 * 256 * 24 = 614 KB

This is trivially small - easily fits in memory on every node.
```

### Load Distribution Mathematics

For `N` physical nodes, each with `V` vnodes, the ring has `N*V` positions. The fraction of the ring owned by any single physical node follows a distribution with:

```
Expected load per node:   1/N
Standard deviation:       1 / sqrt(N * V)
99th percentile load:     1/N + 2.33 / sqrt(N * V)

Example: N=10, V=256
  Expected:     10%
  Std Dev:      1/sqrt(2560) = 1.98%
  99th pctile:  10% + 2.33 * 1.98% ≈ 14.6%
  → Worst-case node handles ~14.6% vs ideal 10% (46% overload in worst case)
```

---

## 4. Algorithm Deep Dive

### Hash Functions for Consistent Hashing

| Hash Function | Output Size | Speed (GB/s) | Uniformity | Use Case |
|---------------|-------------|--------------|------------|----------|
| MD5           | 128-bit     | ~0.4         | Excellent  | Legacy systems (Ketama) |
| SHA-1         | 160-bit     | ~0.5         | Excellent  | Security-sensitive |
| MurmurHash3   | 128-bit     | ~5.0         | Excellent  | Cassandra, general purpose |
| xxHash        | 64/128-bit  | ~10.0        | Excellent  | Performance-critical |
| FNV-1a        | 32/64-bit   | ~3.0         | Good       | Simple implementations |

**Key requirements for the hash function:**
1. **Uniformity** - Output must be uniformly distributed (otherwise ring is unbalanced)
2. **Determinism** - Same input must always produce same output
3. **Speed** - Hashing is on the critical path for every request
4. **Avalanche effect** - Small input change → large output change (prevents clustering)

Cryptographic strength is **NOT required** - this is not a security application.

### Ring Implementation

The ring is implemented as a **sorted array of (hash_position, node_id)** pairs. Key lookup uses binary search.

```
Data Structure:

  ring = sorted_array of (position, node_id)

  Example (simplified positions):
  ┌─────────┬─────────┐
  │Position │ Node    │
  ├─────────┼─────────┤
  │   5     │ N1_v0   │
  │  18     │ N3_v1   │
  │  27     │ N2_v0   │
  │  35     │ N1_v1   │
  │  48     │ N3_v0   │
  │  56     │ N2_v1   │
  │  71     │ N1_v2   │
  │  83     │ N2_v2   │
  │  92     │ N3_v2   │
  └─────────┴─────────┘

  Lookup("my_key"):
    1. h = hash("my_key") = 40
    2. Binary search for first position >= 40
    3. Found: position 48 → N3_v0 → physical node N3
    4. Return N3
```

### Pseudocode Implementation

```python
class ConsistentHashRing:
    def __init__(self, nodes=[], num_vnodes=256, hash_fn=md5):
        self.num_vnodes = num_vnodes
        self.hash_fn = hash_fn
        self.ring = SortedList()          # sorted by position
        self.node_positions = {}          # node -> list of positions (for removal)

        for node in nodes:
            self.add_node(node)

    def _hash(self, key: str) -> int:
        """Hash a key to a position on [0, 2^32)"""
        return int(self.hash_fn(key.encode()).hexdigest(), 16) % (2**32)

    def add_node(self, node: str, weight: int = 1):
        """Add a node with weight * num_vnodes virtual positions"""
        positions = []
        for i in range(self.num_vnodes * weight):
            vnode_key = f"{node}#vn{i}"
            pos = self._hash(vnode_key)
            self.ring.add((pos, node))
            positions.append(pos)
        self.node_positions[node] = positions

    def remove_node(self, node: str):
        """Remove all virtual nodes for a physical node"""
        for pos in self.node_positions[node]:
            self.ring.remove((pos, node))
        del self.node_positions[node]

    def get_node(self, key: str) -> str:
        """Find the node responsible for this key - O(log n)"""
        if not self.ring:
            raise Exception("Ring is empty")

        h = self._hash(key)

        # Binary search: find first position >= h
        idx = self.ring.bisect_left((h,))

        # Wrap around if past the last position
        if idx == len(self.ring):
            idx = 0

        return self.ring[idx][1]  # return node_id

    def get_nodes(self, key: str, n: int) -> list:
        """Get N distinct physical nodes for replication"""
        if not self.ring:
            raise Exception("Ring is empty")

        h = self._hash(key)
        idx = self.ring.bisect_left((h,))

        result = []
        seen = set()
        checked = 0

        while len(result) < n and checked < len(self.ring):
            wrapped_idx = (idx + checked) % len(self.ring)
            node = self.ring[wrapped_idx][1]
            if node not in seen:
                seen.add(node)
                result.append(node)
            checked += 1

        return result
```

### Complexity Analysis

| Operation      | Time        | Space          |
|----------------|-------------|----------------|
| Lookup key     | O(log(N*V)) | -              |
| Add node       | O(V * log(N*V)) | O(V)       |
| Remove node    | O(V * log(N*V)) | -O(V)      |
| Ring storage   | -           | O(N * V)       |

Where N = physical nodes, V = vnodes per node.

For a typical production setup (100 nodes, 256 vnodes):
- Ring size: 25,600 entries
- Lookup: ~15 comparisons (log2(25600) ≈ 14.6)
- This is **sub-microsecond** on modern hardware

### Alternative: TreeMap Implementation

Java's `TreeMap` (Red-Black Tree) provides `ceilingEntry()` for O(log n) "next clockwise" lookup:

```java
TreeMap<Long, String> ring = new TreeMap<>();

String getNode(String key) {
    long hash = hashFunction(key);
    Map.Entry<Long, String> entry = ring.ceilingEntry(hash);
    if (entry == null) {
        entry = ring.firstEntry();  // wrap around
    }
    return entry.getValue();
}
```

---

## 5. Node Addition/Removal

### Adding a Node

When node `N4` is added between `N2` and `N3`, only keys in the arc `(N2, N4]` move from `N3` to `N4`:

```
  BEFORE (3 nodes):                    AFTER (4 nodes, N4 added):

       0                                    0
       |                                    |
       N1                                   N1
      / \                                  / \
     /   \                                /   \
    /     \                              /     \
   |       |                            |       |
   |       |                            |       N4 ← NEW
   |       |                            |      /|
    \     /                              \    / |
     \   /                                \  /  |
      \ /                                  \/   |
       N3────── N2                         N3───N2


  Keys that move: ONLY those in arc (N2 → N4)
  All other keys stay on their current node!

  Detailed view of affected arc:

        N2          N4 (new)       N3
    ────┼─────────────┼─────────────┼────
        │  ↑  ↑  ↑   │  ↑  ↑  ↑   │
        │  K1 K2 K3   │  K4 K5 K6  │
        │             │             │
        │ These move  │ These stay  │
        │ N3 → N4     │ on N3       │
        │             │             │
```

### Fraction of Keys That Move

```
Adding 1 node to N existing nodes:

  Consistent Hashing:  ~K/N keys move  (only keys assigned to new node)
  Modulo Hashing:      ~K*(N/(N+1)) keys move  (almost everything)

  Example with K=1,000,000 keys, N=10 nodes:
  ┌────────────────────┬───────────────────┬────────────────────┐
  │                    │ Consistent Hash   │ Modulo Hash        │
  ├────────────────────┼───────────────────┼────────────────────┤
  │ Keys that move     │ ~100,000 (10%)    │ ~909,091 (91%)     │
  │ Keys that stay     │ ~900,000 (90%)    │ ~90,909 (9%)       │
  │ Network transfer   │ ~10 GB            │ ~91 GB             │
  │ Time (1 Gbps)      │ ~80 sec           │ ~728 sec           │
  └────────────────────┴───────────────────┴────────────────────┘
```

### Removing a Node

When `N2` dies or is decommissioned, all its keys move to the next clockwise node (`N3`):

```
  BEFORE:                              AFTER (N2 removed):

     N1 ─── K1                          N1 ─── K1
    /    \                              /    \
   K6     K2                           K6     K2  ← was on N2, now on N3
   |        \                          |        \
   |     N2 ── K3                      |         K3  ← was on N2, now on N3
   |    /                              |        /
   K5  K4                              K5    K4  ← was on N2, now on N3
    \ /                                 \   /
     N3 ─── K7                           N3 ─── K7

  N2's keys (K2, K3, K4) → all move to N3 (next clockwise)
  N1's keys (K1, K6) and N3's keys (K5, K7) → unchanged
```

### Hot Spot Problem

After removal, the successor node temporarily handles 2x its normal load:

```
  Normal load per node (N=4): 25%

  After 1 node removal:
    - Successor node load: 25% (own) + 25% (inherited) = 50%
    - Other nodes: still 25% each

  With vnodes this is mitigated:
    - 256 vnodes mean 256 small arcs are redistributed
    - Load spreads across MANY successor nodes, not just one
    - Each remaining node picks up ~1/(N-1) of the removed node's load

  Without vnodes:    one node gets 2x load   → potential cascade failure
  With 256 vnodes:   load spreads evenly     → each node gets ~1.33x load (N=4→3)
```

---

## 6. Weighted Consistent Hashing

### Problem: Heterogeneous Hardware

Not all nodes have equal capacity. A node with 64GB RAM and NVMe should handle more keys than one with 16GB RAM and spinning disk.

### Solution: Proportional Virtual Nodes

Assign virtual nodes proportional to capacity:

```
  Node Capacities:
    Server A: 64 GB RAM, 8 cores   → weight = 4
    Server B: 32 GB RAM, 4 cores   → weight = 2
    Server C: 16 GB RAM, 2 cores   → weight = 1

  Virtual Nodes (base = 100 vnodes):
    Server A: 4 * 100 = 400 vnodes → ~57% of ring
    Server B: 2 * 100 = 200 vnodes → ~29% of ring
    Server C: 1 * 100 = 100 vnodes → ~14% of ring

  Ring visualization (simplified, showing density):

    0°──────────90°──────────180°─────────270°─────────360°
    │AAABABAAABA│AABABAABAA│BABAAABACAB│AACABABAACA│
    │           │          │           │           │
    Dense A      Dense A     Mixed       Mixed

  Result: Each server receives load proportional to its weight.
```

### Dynamic Weight Adjustment

When a node becomes slow (e.g., disk degradation), reduce its weight dynamically:

```python
# Detect high latency on Server C
if server_c.p99_latency > threshold:
    ring.update_weight("server_c", new_weight=0.5)  # halve its load
    # Internally: remove half of server_c's vnodes
    # Keys from removed vnodes redistribute to neighbors
```

---

## 7. Jump Consistent Hashing

### Google's O(1) Space Algorithm (2014)

Jump Consistent Hash (Lamping & Veach, 2014) is a fundamentally different approach. Instead of a ring, it uses a mathematical function that directly computes bucket assignment.

```c
int32_t JumpConsistentHash(uint64_t key, int32_t num_buckets) {
    int64_t b = -1, j = 0;
    while (j < num_buckets) {
        b = j;
        key = key * 2862933555777941757ULL + 1;
        j = (b + 1) * (double(1LL << 31) / double((key >> 33) + 1));
    }
    return b;
}
```

### Properties

| Property | Ring-based CH | Jump CH |
|----------|--------------|---------|
| Space    | O(N * V)     | O(1)    |
| Lookup   | O(log(N*V))  | O(ln N) |
| Add node (end only) | O(V log(NV)) | O(1) |
| Remove arbitrary node | O(V log(NV)) | **NOT SUPPORTED** |
| Weighted nodes | Yes (via vnodes) | No (natively) |
| Named nodes | Yes | No (buckets are 0..N-1) |

### Critical Limitation

Jump consistent hashing only supports **appending** nodes at the end. You **cannot** remove an arbitrary node without remapping many keys. Buckets are numbered `0` to `N-1`; removing bucket `3` out of `10` is not supported.

### When to Use Jump CH

**Use Jump CH when:**
- Nodes are numbered sequentially and rarely removed (e.g., sharded databases with planned growth)
- Memory is extremely constrained
- You only add capacity by appending new shards
- No need for rack/DC awareness or replication logic

**Use Ring-based CH when:**
- Nodes can fail and be removed at any time
- You need weighted distribution
- You need rack-aware replica placement
- System is dynamic (auto-scaling, spot instances)

---

## 8. Real-World Implementations

### 8.1 Amazon DynamoDB

DynamoDB uses consistent hashing as the foundation of its partition management:

```
  DynamoDB Partition Ring:

  ┌─────────────────────────────────────────────────────────┐
  │                    Hash Space [0, 2^128)                 │
  │                                                         │
  │   Table "Users" with partition key "user_id"            │
  │                                                         │
  │   Partition 1        Partition 2        Partition 3      │
  │   [0, 2^128/3)      [2^128/3, 2*2^128/3)  [2*2^128/3, 2^128) │
  │       │                    │                    │        │
  │       ▼                    ▼                    ▼        │
  │   ┌────────┐          ┌────────┐          ┌────────┐   │
  │   │Storage │          │Storage │          │Storage │   │
  │   │Node A  │          │Node B  │          │Node C  │   │
  │   │(Leader)│          │(Leader)│          │(Leader)│   │
  │   └───┬────┘          └───┬────┘          └───┬────┘   │
  │       │                   │                   │         │
  │   ┌───┴───┐          ┌───┴───┐          ┌───┴───┐     │
  │   │Rep 1  │          │Rep 1  │          │Rep 1  │     │
  │   │Rep 2  │          │Rep 2  │          │Rep 2  │     │
  │   └───────┘          └───────┘          └───────┘     │
  └─────────────────────────────────────────────────────────┘

  Key routing:
    hash("user_123") = 0x4A3F... → falls in Partition 1 → Storage Node A
```

**DynamoDB specifics:**
- Uses MD5 hash of partition key
- Automatically splits partitions when they exceed 10GB or 3000 RCU/1000 WCU
- Split creates two new partitions from one (hash range bisection)
- Request router maintains partition map in memory (~100μs lookup)

### 8.2 Apache Cassandra

Cassandra's token ring is one of the most well-known consistent hashing implementations:

```
  Cassandra Token Ring (Murmur3Partitioner):
  Hash range: [-2^63, 2^63 - 1]

  Cluster: 4 nodes, RF=3, num_tokens=256

  ┌───────────────────────────────────────────────┐
  │             Gossip Protocol                    │
  │  Every node knows the full token ring map      │
  │                                                │
  │  Node A: tokens {-2^63+1000, -2^63+50000, ...}│  (256 tokens)
  │  Node B: tokens {-2^63+2000, -2^63+51000, ...}│  (256 tokens)
  │  Node C: tokens {-2^63+3000, -2^63+52000, ...}│  (256 tokens)
  │  Node D: tokens {-2^63+4000, -2^63+53000, ...}│  (256 tokens)
  └───────────────────────────────────────────────┘

  Write path for key "user:42":
    1. Coordinator receives write
    2. token = murmur3("user:42") = 7450923840...
    3. Walk ring clockwise → find 3 distinct nodes (RF=3)
    4. Send write to all 3 replicas
    5. Wait for CL (e.g., QUORUM = 2 acks)
```

**Rack-aware placement in Cassandra:**
```
  Ring with rack awareness (RF=3, 2 racks):

       Token:   10     25     40     55     70     85
       Node:    A      B      C      D      E      F
       Rack:    R1     R2     R1     R2     R1     R2

  For key hashing to token 30 (between B and C):
    Replica 1: C (next clockwise)           → Rack R1
    Replica 2: D (next clockwise, new rack) → Rack R2  ✓ different rack
    Replica 3: E (next clockwise, new rack) → Rack R1  (back to R1, but that's ok with RF=3)

  NetworkTopologyStrategy ensures replicas span racks/DCs.
```

### 8.3 Memcached / Redis Cluster

**Memcached (Client-side Ketama):**

The Ketama algorithm is the standard consistent hashing implementation for Memcached clients:

```
  Client-side consistent hashing:

  ┌──────────┐
  │  Client  │──── Maintains the hash ring locally
  └────┬─────┘
       │
       │  get("session:abc")
       │  hash = md5("session:abc") = 0x7F3A...
       │  ring lookup → Server 2
       │
       ├──────────────── Server 1 (192.168.1.1:11211)
       ├──────────────── Server 2 (192.168.1.2:11211) ← direct connection
       └──────────────── Server 3 (192.168.1.3:11211)

  Ketama specifics:
    - 160 vnodes per server (using 4 points per MD5 hash, 40 hashes)
    - Vnode key format: "server_ip:port-index"
    - All clients must use identical ring configuration
```

**Redis Cluster:**

Redis Cluster uses a fixed **16384 hash slot** approach (not a traditional ring):

```
  Redis Cluster Hash Slots:

  hash_slot = CRC16(key) % 16384

  ┌──────────────────────────────────────────────────────┐
  │  Slot range          │  Node                         │
  ├──────────────────────┼──────────────────────────────-┤
  │  0 - 5460            │  Master A (+ Replica A')      │
  │  5461 - 10922        │  Master B (+ Replica B')      │
  │  10923 - 16383       │  Master C (+ Replica C')      │
  └──────────────────────┴───────────────────────────────┘

  Slot migration (adding Node D):
    Move slots 0-4095 from A to D
    → Only keys in slots 0-4095 need to move
    → MIGRATE command moves key-by-key with ASK/MOVED redirects
```

### 8.4 Discord

Discord shards 200M+ users across thousands of guilds (servers):

```
  Discord's Sharding Architecture:

  guild_id = snowflake (64-bit, contains timestamp)
  shard_id = (guild_id >> 22) % num_shards

  ┌──────────────────────────────────────────────────────────┐
  │  Gateway Sharding (WebSocket connections)                 │
  │                                                          │
  │  User connects → assigned to shard based on guild_id     │
  │                                                          │
  │  Shard 0: guilds {0, 1024, 2048, ...}                   │
  │  Shard 1: guilds {1, 1025, 2049, ...}                   │
  │  ...                                                     │
  │  Shard N: guilds {N, N+1024, ...}                       │
  │                                                          │
  │  For data storage (messages, members):                   │
  │  Cassandra ring with consistent hashing                   │
  │  Partition key = channel_id for messages                  │
  │  → Hot channels (announcements) can be split further     │
  └──────────────────────────────────────────────────────────┘
```

Discord uses consistent hashing for their data layer (Cassandra-based) while using a simpler modulo-based sharding for their gateway WebSocket connections (since gateway shards can be reshuffled during deploys).

### 8.5 Akamai CDN

Akamai pioneered consistent hashing (the original 1997 paper by Karger et al. was co-authored by Akamai's founders):

```
  Akamai Content Placement:

  Request: GET /video/movie123.mp4

  1. DNS resolves to nearest Akamai edge cluster
  2. Within cluster, consistent hash determines which server has the content:

     hash("movie123.mp4") → Server 7 in cluster

  ┌─────────────────────────────────────────────────────┐
  │  Edge Cluster (Chicago)                             │
  │                                                     │
  │   ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐   │
  │   │ S1  │  │ S2  │  │ S3  │  │ S4  │  │ S5  │   │
  │   │     │  │     │  │     │  │     │  │     │   │
  │   │vid_A│  │vid_E│  │vid_B│  │vid_D│  │vid_C│   │
  │   │vid_F│  │vid_H│  │vid_G│  │vid_I│  │vid_J│   │
  │   └─────┘  └─────┘  └─────┘  └─────┘  └─────┘   │
  │                                                     │
  │  Benefits:                                          │
  │   - Server failure: only its content re-fetched     │
  │   - No single point of content duplication          │
  │   - Maximize local cache hit rate                   │
  └─────────────────────────────────────────────────────┘

  If Server 3 dies:
    - vid_B, vid_G → now served by Server 4 (next on ring)
    - Server 4 fetches from origin on first miss
    - All other content assignments unchanged
```

### 8.6 Load Balancers (Nginx, HAProxy)

**Nginx upstream consistent hashing:**

```nginx
upstream backend {
    hash $request_uri consistent;    # consistent hashing on URI
    server 10.0.0.1:8080 weight=3;
    server 10.0.0.2:8080 weight=2;
    server 10.0.0.3:8080 weight=1;
}
```

**HAProxy:**

```
backend servers
    balance uri                       # hash the URI
    hash-type consistent              # use consistent hashing (ketama)
    server s1 10.0.0.1:8080 weight 100
    server s2 10.0.0.2:8080 weight 100
    server s3 10.0.0.3:8080 weight 50
```

**Sticky sessions via consistent hashing:**

```
  Client A ─── hash(client_ip) = 0x3F... ─── always → Server 2
  Client B ─── hash(client_ip) = 0x8A... ─── always → Server 5
  Client C ─── hash(client_ip) = 0x1D... ─── always → Server 1

  If Server 2 dies:
    - Client A → remapped to Server 3 (next on ring)
    - Client B, C → unchanged (their server is fine)
    - Only clients on Server 2 lose their session
```

---

## 9. Replication with Consistent Hashing

### N Replicas on Next N Nodes

The standard approach: store each key on the **N successive distinct physical nodes** found by walking clockwise from the key's position.

```
  Replication Factor RF = 3

  Ring with 6 nodes:

              N1 (pos: 0)
             /          \
           N6            N2
          (pos:300)    (pos:60)
           |              |
           |              |
          N5            N3
          (pos:240)    (pos:120)
             \          /
              N4 (pos:180)


  Key K hashes to position 45 (between N1 and N2):

  Replica placement (walk clockwise):
    Primary:    N2 (first node clockwise from pos 45)
    Replica 1:  N3 (second node clockwise)
    Replica 2:  N4 (third node clockwise)

  ┌─────────────────────────────────────────────┐
  │                                             │
  │        N1        K        N2                │
  │   ─────┼─────────↓────────┼────────         │
  │                  45       60                │
  │                            │                │
  │                    ┌───────┘                │
  │                    │                        │
  │                    ▼                        │
  │              ┌──────────┐                   │
  │              │ Primary  │ N2                │
  │              └──────────┘                   │
  │                    │                        │
  │                    ▼                        │
  │              ┌──────────┐                   │
  │              │ Replica1 │ N3                │
  │              └──────────┘                   │
  │                    │                        │
  │                    ▼                        │
  │              ┌──────────┐                   │
  │              │ Replica2 │ N4                │
  │              └──────────┘                   │
  │                                             │
  └─────────────────────────────────────────────┘
```

### Rack/DC Awareness in Replica Placement

Naive "next N nodes" can place all replicas in the same rack (single point of failure). Production systems walk the ring skipping nodes until they find nodes in **different failure domains**.

```
  Rack-Aware Replica Placement (RF=3, 2 DCs, 2 racks each):

  Ring positions:
    pos 10: Node A  (DC1, Rack1)
    pos 25: Node B  (DC1, Rack2)
    pos 40: Node C  (DC2, Rack1)
    pos 55: Node D  (DC2, Rack2)
    pos 70: Node E  (DC1, Rack1)
    pos 85: Node F  (DC1, Rack2)

  Key hashes to position 30. Walk clockwise:

    Candidate 1: Node C (DC2, Rack1)  ← Primary.        DC={DC2}
    Candidate 2: Node D (DC2, Rack2)  ← New rack!       DC={DC2} Rack={R1,R2}
    Candidate 3: Node E (DC1, Rack1)  ← New DC!         ✓ Done.

  Final replicas: C (DC2/R1), D (DC2/R2), E (DC1/R1)
  → Survives: any 1 node failure, any 1 rack failure, any 1 DC failure

  ┌─────────────────────────────────────┐
  │           DC1              DC2       │
  │    ┌──────┬──────┐  ┌──────┬──────┐ │
  │    │Rack1 │Rack2 │  │Rack1 │Rack2 │ │
  │    │      │      │  │      │      │ │
  │    │ [E]  │      │  │ [C]  │ [D]  │ │
  │    │  ↑   │      │  │  ↑   │  ↑   │ │
  │    │  │   │      │  │  │   │  │   │ │
  │    │ Rep2 │      │  │ Pri  │ Rep1 │ │
  │    └──────┴──────┘  └──────┴──────┘ │
  └─────────────────────────────────────┘
```

### Preference List (DynamoDB Style)

DynamoDB maintains a **preference list** for each partition - an ordered list of nodes that should hold replicas, skipping vnodes that map to the same physical node:

```
  Partition key range [A, B]:
    Preference list: [N2, N4, N7, N1, N5]
                      ↑    ↑    ↑    ↑    ↑
                     Primary │    │    │    └─ 5th choice (if 3 fail)
                          2nd  3rd  4th

  On write (W=2, N=3):
    Coordinator sends to N2, N4, N7
    Waits for 2 ACKs (quorum)
    Returns success to client

  On read (R=2, N=3):
    Coordinator reads from N2, N4, N7
    Waits for 2 responses
    Returns most recent version (vector clock comparison)
    Triggers read-repair if versions differ
```

---

## 10. Failure Handling

### Temporary vs Permanent Failure

```
  ┌──────────────────────────────────────────────────────────────┐
  │           Failure Detection & Response                        │
  ├────────────────────┬─────────────────┬───────────────────────┤
  │                    │ Temporary        │ Permanent             │
  │                    │ (network blip,   │ (disk dead, node      │
  │                    │  GC pause, crash) │  decommissioned)     │
  ├────────────────────┼─────────────────┼───────────────────────┤
  │ Detection          │ Gossip timeout   │ Admin command /       │
  │                    │ (e.g., 30s)      │ prolonged absence     │
  ├────────────────────┼─────────────────┼───────────────────────┤
  │ Response           │ Hinted Handoff   │ Ring membership       │
  │                    │ (store hints on  │ change + full         │
  │                    │  coordinator)    │ data streaming        │
  ├────────────────────┼─────────────────┼───────────────────────┤
  │ Ring change?       │ NO               │ YES (remove node)     │
  ├────────────────────┼─────────────────┼───────────────────────┤
  │ Data movement      │ None (hints      │ Successor takes       │
  │                    │  replayed later) │ ownership of ranges   │
  └────────────────────┴─────────────────┴───────────────────────┘
```

### Hinted Handoff (Temporary Failure)

```
  Normal operation:           During N3 failure:

  Client                      Client
    │                           │
    ▼                           ▼
  Coordinator                 Coordinator
    │                           │
    ├──→ N2 (replica 1) ✓      ├──→ N2 (replica 1) ✓
    ├──→ N3 (replica 2) ✓      ├──→ N3 (replica 2) ✗ TIMEOUT
    └──→ N4 (replica 3) ✓      ├──→ N4 (replica 3) ✓
                                └──→ N5 (hint store) ✓  ← "hold this for N3"
                                     │
                                     │  When N3 recovers:
                                     │  N5 replays hints → N3
                                     ▼
                                     N3 receives missed writes
```

### Permanent Node Removal

```
  Timeline of permanent node removal:

  T=0:    N3 fails, gossip marks it "DOWN"
  T=30s:  Still down, hints accumulate on other nodes
  T=10m:  Admin confirms permanent failure
  T=10m:  nodetool removenode N3 (Cassandra)

  Ring state change:
    BEFORE: ..., N2(pos:40), N3(pos:60), N4(pos:80), ...
    AFTER:  ..., N2(pos:40), N4(pos:80), ...

  Data streaming:
    - N3's primary range (40,60] → now owned by N4
    - N4 already had this data as replica (if RF≥2)
    - N4 promotes from "replica" to "primary" for that range
    - If RF=3 and we lost a replica, a NEW replica is created on N5
      by streaming from existing replicas

  ┌──────────────────────────────────────────────────┐
  │  Repair after N3 removal (RF=3):                 │
  │                                                  │
  │  Range (40,60] was on: N3(pri), N4(rep), N5(rep) │
  │  Now must be on:       N4(pri), N5(rep), N6(rep) │
  │                                     ↑            │
  │                               NEW replica        │
  │                          (streamed from N4 or N5) │
  └──────────────────────────────────────────────────┘
```

### Sloppy Quorum (Dynamo-style)

In systems like DynamoDB and Riak, writes can succeed even when the "correct" nodes are down, by writing to the next available nodes on the ring (sloppy quorum). This prioritizes availability over strict consistency.

```
  Strict quorum:   W + R > N  (always consistent)
  Sloppy quorum:   Write to ANY N healthy nodes reachable

  Trade-off: Higher availability, but may need read-repair/anti-entropy
             to fix inconsistencies after partition heals
```

---

## 11. Architect's Guide

### When to Use Consistent Hashing

| Use Case | Consistent Hashing? | Why |
|----------|---------------------|-----|
| Distributed cache (Memcached, Redis) | Yes | Minimize cache invalidation on scale events |
| Database sharding (Cassandra, Dynamo) | Yes | Minimize data movement on rebalance |
| CDN content routing | Yes | Maximize cache hit ratio per edge server |
| Load balancer sticky sessions | Yes | Minimize session loss on backend changes |
| Distributed task queues | Maybe | Only if worker affinity matters |
| Static shard assignment | No | If you never resize, modulo is simpler |
| Ordered data (range queries) | No | Use range-based partitioning instead |

### Decision Matrix: Which Algorithm?

```
  ┌─────────────────────────────────────────────────────────────────┐
  │                                                                 │
  │  Need to remove arbitrary nodes? ──── NO ──→ Jump Consistent   │
  │         │                                     Hash (Google)     │
  │         YES                                                     │
  │         │                                                       │
  │         ▼                                                       │
  │  Need replica placement logic? ──── NO ──→ Ring-based CH       │
  │         │                                   (basic Ketama)      │
  │         YES                                                     │
  │         │                                                       │
  │         ▼                                                       │
  │  Need failure-domain awareness? ── NO ──→ Ring + preference     │
  │         │                                  list (Dynamo-style)  │
  │         YES                                                     │
  │         │                                                       │
  │         ▼                                                       │
  │  Hierarchical topology (tree)? ─── NO ──→ Ring + rack-aware    │
  │         │                                  placement (Cassandra)│
  │         YES                                                     │
  │         │                                                       │
  │         ▼                                                       │
  │  CRUSH Algorithm (Ceph)                                         │
  │  - Pseudo-random placement via hierarchy                        │
  │  - No ring; uses cluster map + deterministic function           │
  │  - Understands: rows, racks, hosts, OSDs                        │
  │                                                                 │
  └─────────────────────────────────────────────────────────────────┘
```

### Alternatives to Consistent Hashing

#### Rendezvous Hashing (Highest Random Weight)

```python
def get_node(key, nodes):
    """Each key picks the node that gives it the highest hash score"""
    return max(nodes, key=lambda node: hash(f"{key}:{node}"))
```

**Properties:**
- O(N) per lookup (must compute hash for all nodes)
- Minimal disruption: only keys on a removed node move
- No ring structure, no vnodes needed
- Simple to implement and reason about
- Works well when N < 100 (O(N) is fine)

**Used by:** Microsoft Azure, some CDN systems, Windows MSFT NLB

#### CRUSH Algorithm (Ceph)

Ceph's Controlled Replication Under Scalable Hashing:

```
  CRUSH Map (hierarchical):

        root (default)
       /            \
    rack1           rack2
    /   \           /   \
  host1  host2   host3  host4
  /|\     /|\    /|\     /|\
 osd osd  osd   osd osd  osd

  Placement rule:
    "Take 1 from rack1, 1 from rack2, 1 from any"
    → Deterministic, no central lookup, topology-aware
```

**CRUSH vs Consistent Hashing:**
- CRUSH encodes physical topology directly
- No ring; uses pseudorandom function with cluster map
- Supports complex placement policies ("2 replicas in different racks in same DC, 1 in remote DC")
- Preferred for block storage (large objects, few lookups)
- Consistent hashing preferred for key-value stores (many small lookups)

### Production Checklist

```
  Before deploying consistent hashing:

  □ Choose hash function (MurmurHash3 for most cases)
  □ Decide vnode count (start with 256, tune based on cluster size)
  □ Implement ring as sorted array with binary search
  □ Define replication strategy (SimpleStrategy vs NetworkTopologyStrategy)
  □ Implement hinted handoff for temporary failures
  □ Plan for anti-entropy repair (Merkle trees for divergence detection)
  □ Monitor load distribution (alert if any node > 1.5x average)
  □ Test node addition with production-like data distribution
  □ Implement graceful node drain before removal
  □ Ensure all clients see consistent ring state (gossip convergence)
```

---

## Summary

```
  The Evolution of Distributed Hashing:

  Modulo Hashing          Consistent Hashing        Advanced
  (1990s)                 (1997, Karger et al.)     (2010s+)
  ─────────────────────── ──────────────────────── ─────────────────
  hash(k) % N             Ring + clockwise walk     Jump CH (Google)
  Simple                  Vnodes for balance        CRUSH (Ceph)
  ALL keys move           Only K/N keys move        Rendezvous
  Unusable at scale       Industry standard         Special cases

  Key insight: Map nodes AND keys to the same space.
  Walk clockwise → minimal disruption on topology changes.
  Virtual nodes → statistical balance despite few physical nodes.
```

---

## References

1. Karger, D. et al. (1997) "Consistent Hashing and Random Trees" - The original MIT/Akamai paper
2. DeCandia, G. et al. (2007) "Dynamo: Amazon's Highly Available Key-value Store" - SOSP
3. Lakshman, A. & Malik, P. (2010) "Cassandra - A Decentralized Structured Storage System"
4. Lamping, J. & Veach, E. (2014) "A Fast, Minimal Memory, Consistent Hash Algorithm" (Jump CH)
5. Weil, S. et al. (2006) "CRUSH: Controlled, Scalable, Decentralized Placement of Replicated Data"
