# Bloom Filters: Probabilistic Membership Testing at Scale

## 1. Problem Statement

**The fundamental question**: "Is element X in set S?" — when S contains billions of elements.

**Why this is hard at scale**:
- A set of 1 billion URLs occupies ~60 GB in a hash set
- Checking disk/network for every query is too slow (10ms disk, 1ms network)
- We need sub-microsecond answers with minimal memory

**The Bloom Filter trade-off**:
- Answer "definitely NOT in set" with 100% certainty
- Answer "probably in set" with configurable false positive rate (e.g., 1%)
- Use ~1.2 GB instead of 60 GB (for 1B elements at 1% FP rate)

```
┌─────────────────────────────────────────────────────────────────┐
│                    MEMBERSHIP TESTING SPECTRUM                    │
├──────────────────┬──────────────────┬───────────────────────────┤
│   Hash Set       │  Bloom Filter    │  Linear Scan              │
│   O(n) space     │  O(n) bits       │  O(1) space               │
│   O(1) lookup    │  O(k) lookup     │  O(n) lookup              │
│   Exact          │  Probabilistic   │  Exact                    │
│   60 GB          │  1.2 GB          │  60 GB on disk            │
└──────────────────┴──────────────────┴───────────────────────────┘
```

---

## 2. Core Data Structure

A Bloom filter consists of:
- **Bit array** of `m` bits (all initialized to 0)
- **k** independent hash functions, each mapping elements to positions [0, m-1]

### 2.1 Insertion

To insert element `x`: compute h₁(x), h₂(x), ..., hₖ(x) and set those bits to 1.

```
    Element: "hello"
    Hash functions: k = 3
    Bit array size: m = 16

    h₁("hello") = 2
    h₂("hello") = 7
    h₃("hello") = 13

    Bit Array (before):
    ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┐
    │ 0 │ 0 │ 0 │ 0 │ 0 │ 0 │ 0 │ 0 │ 0 │ 0 │ 0 │ 0 │ 0 │ 0 │ 0 │ 0 │
    └───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┘
      0   1   2   3   4   5   6   7   8   9  10  11  12  13  14  15

    Bit Array (after inserting "hello"):
    ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┐
    │ 0 │ 0 │ 1 │ 0 │ 0 │ 0 │ 0 │ 1 │ 0 │ 0 │ 0 │ 0 │ 0 │ 1 │ 0 │ 0 │
    └───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┘
      0   1   2   3   4   5   6   7   8   9  10  11  12  13  14  15
              ▲                   ▲                       ▲
              │                   │                       │
           h₁("hello")=2     h₂("hello")=7         h₃("hello")=13
```

### 2.2 Inserting Multiple Elements

```
    After inserting "hello" AND "world":

    h₁("world") = 1,  h₂("world") = 7,  h₃("world") = 11

    ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┐
    │ 0 │ 1 │ 1 │ 0 │ 0 │ 0 │ 0 │ 1 │ 0 │ 0 │ 0 │ 1 │ 0 │ 1 │ 0 │ 0 │
    └───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┘
      0   1   2   3   4   5   6   7   8   9  10  11  12  13  14  15
          ▲   ▲                   ▲           ▲       ▲
          │   │                   │           │       │
          │   └─ h₁("hello")     │           │       └─ h₃("hello")
          │                       │           │
          └── h₁("world")        └── h₂("hello")    
                                      h₂("world")  ← SHARED BIT!
                                                └── h₃("world")
    
    Note: Position 7 is shared by both elements (bit collision)
```

### 2.3 Lookup

To check if `x` is in the set: compute all k hashes and check if ALL bits are 1.

```
    Query: "hello" → h₁=2, h₂=7, h₃=13

    ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┐
    │ 0 │ 1 │ 1 │ 0 │ 0 │ 0 │ 0 │ 1 │ 0 │ 0 │ 0 │ 1 │ 0 │ 1 │ 0 │ 0 │
    └───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┘
              ✓                   ✓                       ✓
    
    All 3 bits are SET → "PROBABLY IN SET" ✓


    Query: "foo" → h₁=3, h₂=9, h₃=14

    ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┐
    │ 0 │ 1 │ 1 │ 0 │ 0 │ 0 │ 0 │ 1 │ 0 │ 0 │ 0 │ 1 │ 0 │ 1 │ 0 │ 0 │
    └───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┘
                ✗               ✗                           ✗
    
    At least one bit is NOT set → "DEFINITELY NOT IN SET" ✗
    (We can stop at the first 0 — short circuit)
```

### 2.4 Why False Positives Occur

```
    Elements inserted: "hello", "world"
    
    Query: "phantom" → h₁=1, h₂=2, h₃=13

    ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┐
    │ 0 │ 1 │ 1 │ 0 │ 0 │ 0 │ 0 │ 1 │ 0 │ 0 │ 0 │ 1 │ 0 │ 1 │ 0 │ 0 │
    └───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┘
          ✓   ✓                                           ✓
          │   │                                           │
          │   └─ Set by "hello"                           └─ Set by "hello"
          └── Set by "world"
    
    All bits happen to be 1 due to OTHER elements!
    → FALSE POSITIVE: "phantom" was never inserted, but filter says "probably yes"

    ╔══════════════════════════════════════════════════════════════════╗
    ║  FALSE POSITIVE = All k bit positions coincidentally set by     ║
    ║                   the combination of other inserted elements    ║
    ╚══════════════════════════════════════════════════════════════════╝
```

### 2.5 Why False Negatives NEVER Occur

```
    PROOF BY CONTRADICTION:

    Assume element X was inserted but the filter says "not present."

    1. X was inserted → h₁(X), h₂(X), ..., hₖ(X) were ALL set to 1
    2. Bits are NEVER cleared (no deletion in standard bloom filter)
    3. Therefore ALL k bits for X remain 1 forever
    4. Lookup checks those SAME k positions → all return 1
    5. Filter returns "probably present" → CONTRADICTION

    ┌──────────────────────────────────────────────────────────────┐
    │  INVARIANT: Once a bit is set to 1, it NEVER returns to 0   │
    │  THEREFORE: An inserted element's bits are always all 1     │
    │  THEREFORE: Lookup for an inserted element always succeeds  │
    │  THEREFORE: False negatives are IMPOSSIBLE                  │
    └──────────────────────────────────────────────────────────────┘
```

---

## 3. Mathematics

### 3.1 False Positive Probability

After inserting `n` elements into a bit array of `m` bits using `k` hash functions:

**Probability a specific bit is still 0:**

```
    P(bit = 0) = (1 - 1/m)^(kn) ≈ e^(-kn/m)
```

**Probability of a false positive** (all k bits happen to be 1 for an element NOT in set):

```
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║    FP = (1 - e^(-kn/m))^k                                ║
    ║                                                           ║
    ║    Where:                                                 ║
    ║      m = number of bits in the filter                     ║
    ║      n = number of inserted elements                      ║
    ║      k = number of hash functions                         ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
```

### 3.2 Optimal Number of Hash Functions

Minimizing FP probability with respect to k:

```
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║    k_optimal = (m/n) × ln(2) ≈ 0.693 × (m/n)            ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝

    At optimal k, exactly 50% of bits are set to 1.
    This is the sweet spot — too few hash functions means not enough
    discrimination, too many means the array fills up too fast.
```

### 3.3 Space Requirement for Given FP Rate

Given desired false positive rate `p` and `n` elements:

```
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║    m = -n × ln(p) / (ln(2))²                             ║
    ║      ≈ -1.44 × n × log₂(p)                              ║
    ║                                                           ║
    ║    Bits per element = -1.44 × log₂(p)                    ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝

    ┌──────────────┬────────────────┬──────────────────────┐
    │  FP Rate (p) │ Bits/element   │ Optimal k            │
    ├──────────────┼────────────────┼──────────────────────┤
    │  50%         │  1.44          │  1                   │
    │  10%         │  4.79          │  3.32 → 3            │
    │  1%          │  9.58          │  6.64 → 7            │
    │  0.1%        │  14.37         │  9.97 → 10           │
    │  0.01%       │  19.17         │  13.29 → 13          │
    └──────────────┴────────────────┴──────────────────────┘
```

### 3.4 Comparison with Hash Tables

```
    Storing 1 billion elements:

    ┌────────────────────────┬──────────────────┬────────────────────┐
    │  Data Structure        │  Memory           │  Notes             │
    ├────────────────────────┼──────────────────┼────────────────────┤
    │  HashSet<String>       │  ~60 GB           │  Stores actual     │
    │  (avg 40-byte keys)    │  (40+24)*1B       │  keys + overhead   │
    ├────────────────────────┼──────────────────┼────────────────────┤
    │  HashSet<SHA-1>        │  ~28 GB           │  20-byte hashes    │
    │                        │  (20+8)*1B        │  + pointers        │
    ├────────────────────────┼──────────────────┼────────────────────┤
    │  Bloom Filter (1% FP)  │  ~1.2 GB          │  9.58 bits/elem    │
    │                        │  9.58*1B/8        │  No key storage!   │
    ├────────────────────────┼──────────────────┼────────────────────┤
    │  Bloom Filter (0.1% FP)│  ~1.8 GB          │  14.37 bits/elem   │
    └────────────────────────┴──────────────────┴────────────────────┘

    Space savings: 20-50× compared to hash sets
    Trade-off: Cannot retrieve elements, cannot delete, has false positives
```

### 3.5 Worked Examples

**Example 1: Email spam filter**
```
    Given:
      - 1 million known spam email hashes (n = 1,000,000)
      - Acceptable FP rate: 1% (p = 0.01)

    Calculate:
      m = -1,000,000 × ln(0.01) / (ln(2))²
        = -1,000,000 × (-4.605) / 0.4805
        = 9,585,058 bits ≈ 1.14 MB

      k = (m/n) × ln(2) = 9.585 × 0.693 = 6.64 → 7

    Result: 1.14 MB filter with 7 hash functions
    Compare: HashSet would need ~40 MB (40 bytes × 1M)
    Savings: 35×
```

**Example 2: URL deduplication in web crawler**
```
    Given:
      - 10 billion URLs (n = 10,000,000,000)
      - Acceptable FP rate: 0.1% (p = 0.001)

    Calculate:
      m = -10B × ln(0.001) / (ln(2))²
        = -10B × (-6.908) / 0.4805
        = 143,775,874,818 bits ≈ 16.7 GB

      k = (m/n) × ln(2) = 14.38 × 0.693 = 9.97 → 10

    Result: 16.7 GB filter with 10 hash functions
    Compare: HashSet would need ~600 GB
    Savings: 36×
```

---

## 4. Variants

### 4.1 Counting Bloom Filter

Replaces each bit with a counter (typically 4 bits), enabling deletion.

```
    Standard Bloom Filter (1 bit per cell):
    ┌───┬───┬───┬───┬───┬───┬───┬───┐
    │ 0 │ 1 │ 1 │ 0 │ 1 │ 0 │ 1 │ 0 │
    └───┴───┴───┴───┴───┴───┴───┴───┘

    Counting Bloom Filter (4 bits per cell):
    ┌───┬───┬───┬───┬───┬───┬───┬───┐
    │ 0 │ 2 │ 1 │ 0 │ 3 │ 0 │ 1 │ 0 │
    └───┴───┴───┴───┴───┴───┴───┴───┘

    Insert("x"): increment counters at h₁(x), h₂(x), ..., hₖ(x)
    Delete("x"): decrement counters at h₁(x), h₂(x), ..., hₖ(x)
    Lookup("x"): all counters > 0?

    Trade-off: 4× more space (4 bits vs 1 bit per cell)
    Risk: Counter overflow (4-bit max = 15), extremely rare in practice
```

### 4.2 Scalable Bloom Filter

Grows dynamically by chaining multiple bloom filters of increasing size.

```
    ┌──────────────────────────────────────────────────────────┐
    │                  Scalable Bloom Filter                     │
    │                                                           │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
    │  │  Filter 0   │  │  Filter 1   │  │  Filter 2   │      │
    │  │  FP = p₀    │  │  FP = p₀×r  │  │  FP = p₀×r²│      │
    │  │  m₀ bits    │  │  m₁ bits    │  │  m₂ bits    │      │
    │  │  (full)     │  │  (full)     │  │  (active)   │      │
    │  └─────────────┘  └─────────────┘  └─────────────┘      │
    │                                                           │
    │  Insert: Add to active (rightmost) filter                 │
    │  Lookup: Check ALL filters (OR logic)                     │
    │  When active fills up: create new filter with tighter FP  │
    │                                                           │
    │  Overall FP ≤ p₀ × (1/(1-r)) — geometric series bound    │
    │  Typical r = 0.5 → overall FP ≤ 2×p₀                     │
    └──────────────────────────────────────────────────────────┘
```

### 4.3 Cuckoo Filter

Uses cuckoo hashing with fingerprints stored in buckets.

```
    ┌──────────────────────────────────────────────────────┐
    │              Cuckoo Filter Structure                   │
    │                                                       │
    │  Bucket Array (each bucket holds b fingerprints):     │
    │                                                       │
    │  ┌──────────┬──────────┬──────────┬──────────┐       │
    │  │ Bucket 0 │ Bucket 1 │ Bucket 2 │ Bucket 3 │  ...  │
    │  ├──────────┼──────────┼──────────┼──────────┤       │
    │  │ fp_a     │ fp_c     │ [empty]  │ fp_e     │       │
    │  │ fp_b     │ [empty]  │ fp_d     │ [empty]  │       │
    │  │ [empty]  │ [empty]  │ [empty]  │ [empty]  │       │
    │  │ [empty]  │ [empty]  │ [empty]  │ [empty]  │       │
    │  └──────────┴──────────┴──────────┴──────────┘       │
    │                                                       │
    │  Insert(x):                                           │
    │    fp = fingerprint(x)                                │
    │    i₁ = hash(x)                                      │
    │    i₂ = i₁ ⊕ hash(fp)   ← partial-key cuckoo        │
    │    Place fp in bucket[i₁] or bucket[i₂]              │
    │    If both full → evict & relocate (cuckoo style)    │
    │                                                       │
    │  Delete(x): Remove fp from bucket[i₁] or bucket[i₂]  │
    └──────────────────────────────────────────────────────┘

    Advantages over Bloom Filter:
    - Supports deletion (without counting overhead)
    - Better space efficiency at FP < 3%
    - Better locality (fewer memory accesses)
```

### 4.4 Quotient Filter

Cache-friendly, supports deletion and merging.

```
    Uses quotienting: hash(x) split into quotient q and remainder r
    
    Stores remainders in a compact hash table using linear probing
    with 3 metadata bits per slot (is_occupied, is_continuation, is_shifted)

    ┌─────┬───┬───┬───┬──────────────┐
    │ Slot│ O │ C │ S │  Remainder   │
    ├─────┼───┼───┼───┼──────────────┤
    │  0  │ 1 │ 0 │ 0 │  r₁          │  ← canonical slot for q=0
    │  1  │ 0 │ 0 │ 0 │  [empty]     │
    │  2  │ 1 │ 0 │ 0 │  r₃          │  ← canonical slot for q=2
    │  3  │ 1 │ 1 │ 1 │  r₄          │  ← shifted run continuation
    │  4  │ 0 │ 0 │ 1 │  r₅          │  ← shifted from slot 3
    └─────┴───┴───┴───┴──────────────┘

    Advantages: Mergeable, resizable, cache-friendly, supports deletion
    Disadvantage: Slightly more complex implementation
```

### 4.5 Blocked Bloom Filter

Partitions the bit array into cache-line-sized blocks.

```
    Traditional Bloom Filter (random access across entire array):
    ┌─────────────────────────────────────────────────────────────┐
    │ xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx │
    └─────────────────────────────────────────────────────────────┘
    Access: k random positions → k cache misses (worst case)

    Blocked Bloom Filter (each block = 1 cache line = 64 bytes = 512 bits):
    ┌────────────┬────────────┬────────────┬────────────┬─────┐
    │  Block 0   │  Block 1   │  Block 2   │  Block 3   │ ... │
    │  512 bits  │  512 bits  │  512 bits  │  512 bits  │     │
    └────────────┴────────────┴────────────┴────────────┴─────┘

    Insert(x): block_id = hash₀(x) mod num_blocks
               Set k bits WITHIN that single block
    
    Result: At most 1 cache miss per lookup (vs k for standard)
    Trade-off: Slightly higher FP rate (~1.5-2× for same space)
```

### 4.6 Ribbon Filter

RocksDB's modern replacement (2021). Uses a ribbon (banded matrix) solved via Gaussian elimination.

```
    Key insight: Treat filter construction as solving a system of 
    linear equations over GF(2)

    - Each element defines a sparse equation (ribbon width w ≈ 128)
    - Solutions stored as compact coefficient rows
    - Query: compute dot product, check result bits

    Advantages:
    - ~30% more space-efficient than standard Bloom at same FP rate
    - Construction is slower (Gaussian elimination) but queries are fast
    - Better suited for static/immutable datasets (LSM levels)
    
    Used in: RocksDB 6.15+ (configurable per SST level)
```

### 4.7 Comparison Table

```
┌─────────────────┬────────┬────────┬────────┬─────────┬──────────┬───────────┐
│ Variant         │Delete? │Dynamic?│ Space  │Locality │ FP Rate  │ Use Case  │
├─────────────────┼────────┼────────┼────────┼─────────┼──────────┼───────────┤
│ Standard Bloom  │  No    │  No    │ 1×     │ Poor    │ Baseline │ General   │
│ Counting Bloom  │  Yes   │  No    │ 3-4×   │ Poor    │ Same     │ Deletion  │
│ Scalable Bloom  │  No    │  Yes   │ ~1.1×  │ Poor    │ ~2× base │ Unknown n │
│ Cuckoo Filter   │  Yes   │  No    │ 0.7-1× │ Good    │ Better   │ High load │
│ Quotient Filter │  Yes   │  Yes   │ 1-1.2× │ Great   │ Same     │ Streaming │
│ Blocked Bloom   │  No    │  No    │ 1×     │ Great   │ ~1.5×    │ CPU-bound │
│ Ribbon Filter   │  No    │  No    │ 0.7×   │ Good    │ Better   │ Static/LSM│
└─────────────────┴────────┴────────┴────────┴─────────┴──────────┴───────────┘
```

---

## 5. Distributed Applications

### 5.1 Reducing Unnecessary Disk I/O

```
    ┌─────────────────────────────────────────────────────────────────┐
    │             LSM-Tree with Bloom Filters                          │
    │                                                                  │
    │   Query: GET("user:12345")                                       │
    │                                                                  │
    │   ┌──────────┐                                                   │
    │   │ MemTable │ ← Check in-memory (fast)                         │
    │   └────┬─────┘                                                   │
    │        │ Miss                                                     │
    │        ▼                                                         │
    │   ┌──────────┐  ┌─────────────┐                                 │
    │   │ SSTable 0│◄─┤Bloom Filter │ → "NOT HERE" → Skip! (saved 1 I/O)
    │   └────┬─────┘  └─────────────┘                                 │
    │        │                                                         │
    │        ▼                                                         │
    │   ┌──────────┐  ┌─────────────┐                                 │
    │   │ SSTable 1│◄─┤Bloom Filter │ → "MAYBE HERE" → Read from disk │
    │   └────┬─────┘  └─────────────┘                                 │
    │        │                                                         │
    │        ▼                                                         │
    │   ┌──────────┐  ┌─────────────┐                                 │
    │   │ SSTable 2│◄─┤Bloom Filter │ → "NOT HERE" → Skip!            │
    │   └──────────┘  └─────────────┘                                 │
    │                                                                  │
    │   Without bloom filters: 3 disk reads                            │
    │   With bloom filters: 1 disk read + 3 bloom checks (in-memory)  │
    └─────────────────────────────────────────────────────────────────┘
```

### 5.2 Reducing Network Calls

```
    ┌────────────────────────────────────────────────────────────────┐
    │          Distributed Key-Value Store (e.g., Cassandra)          │
    │                                                                 │
    │   Client: GET("user:999")                                       │
    │                                                                 │
    │   Coordinator Node                                              │
    │      │                                                          │
    │      ├── Node A: Bloom says "NO"  → Don't send network request  │
    │      ├── Node B: Bloom says "YES" → Send request → Found!       │
    │      └── Node C: Bloom says "NO"  → Don't send network request  │
    │                                                                  │
    │   Saved: 2 network round-trips (~2ms each)                       │
    └────────────────────────────────────────────────────────────────┘
```

### 5.3 Distributed Cache Coordination

```
    ┌───────────────────────────────────────────────────────────┐
    │      Summary Cache (Squid Proxy Example)                   │
    │                                                            │
    │  Each proxy maintains a Bloom filter of its cached URLs    │
    │  Periodically exchanges Bloom filters with peers           │
    │                                                            │
    │  ┌─────────┐     ┌─────────┐     ┌─────────┐            │
    │  │ Proxy A │◄───►│ Proxy B │◄───►│ Proxy C │            │
    │  │ BF: A   │     │ BF: B   │     │ BF: C   │            │
    │  │ Has BF  │     │ Has BF  │     │ Has BF  │            │
    │  │ of B, C │     │ of A, C │     │ of A, B │            │
    │  └─────────┘     └─────────┘     └─────────┘            │
    │                                                            │
    │  On cache miss at Proxy A:                                 │
    │    Check BF_B → "URL maybe in B" → Ask B                  │
    │    Check BF_C → "URL not in C"   → Don't ask C            │
    └───────────────────────────────────────────────────────────┘
```

### 5.4 Network Routing

```
    ┌─────────────────────────────────────────────────────────────┐
    │       Content-Based Routing with Bloom Filters               │
    │                                                              │
    │   Publisher-Subscriber System:                                │
    │                                                              │
    │   Each router maintains a Bloom filter of subscribed topics  │
    │   for each outgoing link                                     │
    │                                                              │
    │              ┌────────────┐                                   │
    │              │   Router   │                                   │
    │              │            │                                   │
    │         ┌────┴────┬───────┴────┐                             │
    │         │         │            │                              │
    │    ┌────┴───┐ ┌───┴────┐ ┌────┴───┐                         │
    │    │ Link 1 │ │ Link 2 │ │ Link 3 │                         │
    │    │BF:sport│ │BF:tech │ │BF:news │                         │
    │    └────────┘ └────────┘ └────────┘                          │
    │                                                              │
    │   Message topic="sports/nba" → Check each link's BF         │
    │   → Forward only to Link 1 (not Links 2, 3)                 │
    └─────────────────────────────────────────────────────────────┘
```

---

## 6. Real-World Implementations

### 6.1 Apache Cassandra

```
    SSTable Bloom Filters:
    - Each SSTable has an associated Bloom filter
    - Default FP rate: 1% (configurable per table)
    - Saves ~1 disk seek per negative lookup
    - Stored in memory (loaded at startup from -Filter.db file)
    
    Configuration:
      CREATE TABLE users (...)
      WITH bloom_filter_fp_chance = 0.01;  -- 1% FP rate
    
    Sizing: For 1M rows at 1% FP → ~1.14 MB per SSTable filter
    
    Impact: Reduces read latency from ~10ms (disk) to ~10μs (bloom check)
    for queries where the key doesn't exist on that SSTable.
```

### 6.2 Google Bigtable / LevelDB / RocksDB

```
    LSM-Tree Level Filters:
    
    ┌─────────────────────────────────────────────┐
    │  Level 0: 4 SSTables × BF (10% FP each)    │  ← High FP OK (few files)
    │  Level 1: 10 SSTables × BF (1% FP each)    │
    │  Level 2: 100 SSTables × BF (1% FP each)   │
    │  Level 3: 1000 SSTables × BF (0.1% FP)     │  ← Tighter at bottom
    └─────────────────────────────────────────────┘
    
    RocksDB specifics:
    - Full filter (one per SSTable) or partitioned filter (one per block)
    - Partitioned filters allow partial loading → less memory pressure
    - Ribbon filters available since RocksDB 6.15 (2021)
    - Configurable bits_per_key (default 10 → ~1% FP)
    
    LevelDB: ~10 bits/key, stored at end of each .sst file
```

### 6.3 Apache HBase

```
    Block-level Bloom Filters:
    - Filter per HFile block (not per HFile)
    - Supports ROW and ROWCOL bloom types
    - ROW: Tests if row key exists in block
    - ROWCOL: Tests if row+column combination exists
    
    Configuration:
      create 'table', {NAME => 'cf', BLOOMFILTER => 'ROW'}
    
    Particularly effective for:
    - Random read workloads (Get operations)
    - When table has many StoreFiles (before compaction)
```

### 6.4 Akamai CDN — One-Hit-Wonder Filter

```
    Problem: 75% of web objects are accessed only ONCE.
             Caching them wastes memory.

    Solution: Two-tier filtering
    
    ┌────────────────────────────────────────────────────┐
    │                                                     │
    │   Request for URL                                   │
    │       │                                             │
    │       ▼                                             │
    │   ┌──────────────────┐                              │
    │   │ Check Bloom Filter│                             │
    │   │ "Seen before?"    │                             │
    │   └────────┬─────────┘                              │
    │            │                                        │
    │     ┌──── │ ────┐                                   │
    │     │ NO         │ YES                              │
    │     ▼            ▼                                  │
    │   Add to BF    Cache the                            │
    │   Don't cache  object                               │
    │   (one-hit     (second+ access                      │
    │    wonder)      = worth caching)                    │
    │                                                     │
    └────────────────────────────────────────────────────┘

    Result: Eliminated ~75% of unnecessary cache writes
    Published: "Caching the Uncacheable" (IMC 2017)
```

### 6.5 Google Chrome — Safe Browsing

```
    Problem: Check every URL against millions of known malicious URLs
             without sending every URL to Google's servers (privacy!)

    Solution:
    1. Local Bloom filter (~25MB) containing hashes of malicious URLs
    2. On URL visit:
       - Check local Bloom filter
       - If "NO" → Safe, proceed (majority of lookups)
       - If "MAYBE" → Send hash prefix to Google API for confirmation
    
    This avoids:
    - Sending all browsing URLs to Google (privacy)
    - Blocking page load for network round-trip (performance)
    
    Only ~0.1% of URLs trigger the network check (FP + actual matches)
```

### 6.6 Bitcoin — SPV Client Transaction Filtering

```
    Lightweight (SPV) clients can't download all transactions.
    They create a Bloom filter of their addresses and send to full nodes.

    Full Node                          SPV Client
    ┌──────────┐                       ┌──────────┐
    │          │◄── filterload ────────│ BF of my │
    │ All txns │                       │ addresses │
    │          │─── merkleblock ──────►│          │
    │          │    (matching txns     │ Only my  │
    │          │     + merkle proof)   │ txns!    │
    └──────────┘                       └──────────┘

    Privacy trade-off: Full node learns approximate set of client's addresses
    (due to false positives providing plausible deniability)
    
    BIP 37 (deprecated in favor of BIP 157/158 compact block filters)
```

### 6.7 Medium — Avoiding Already-Read Articles

```
    Per-user Bloom filter of article IDs they've already seen.
    When generating recommendations:
    - Check each candidate article against user's Bloom filter
    - If "probably seen" → exclude from recommendations
    - If "definitely not seen" → include as candidate
    
    False positives (excluding unseen articles) are acceptable:
    - User misses occasional article (low impact)
    - Better than re-showing already-read content (annoying)
```

### 6.8 Ethereum — Log Bloom Filters in Block Headers

```
    Each block header contains a 2048-bit Bloom filter (logsBloom)
    encoding all log entries (events) in that block.

    ┌─────────────────────────────────────┐
    │         Block Header                 │
    │  ...                                 │
    │  logsBloom: 2048-bit Bloom filter    │
    │  Contains: contract addresses +      │
    │            event topics from all     │
    │            transaction receipts      │
    └─────────────────────────────────────┘

    Light client searching for events:
    1. Download block headers (80 bytes each)
    2. Check logsBloom for target address/topic
    3. Only download full receipts for matching blocks
    
    Saves: Downloading receipts for ~99% of irrelevant blocks
```

---

## 7. Implementation Details

### 7.1 Hash Function Selection

```
    Requirements for Bloom filter hash functions:
    - Fast (computed k times per operation)
    - Uniform distribution
    - Independent (or approximately so)
    - NOT cryptographic (too slow, security unnecessary)

    ┌──────────────────┬────────────┬───────────────┬──────────────┐
    │ Hash Function    │ Speed      │ Quality       │ Used In      │
    ├──────────────────┼────────────┼───────────────┼──────────────┤
    │ MurmurHash3      │ ~3 GB/s    │ Excellent     │ Cassandra,   │
    │ (128-bit)        │            │               │ HBase        │
    ├──────────────────┼────────────┼───────────────┼──────────────┤
    │ xxHash           │ ~6 GB/s    │ Excellent     │ RocksDB,     │
    │ (64/128-bit)     │            │               │ LZ4          │
    ├──────────────────┼────────────┼───────────────┼──────────────┤
    │ CityHash         │ ~5 GB/s    │ Excellent     │ Google       │
    │ (64/128/256-bit) │            │               │ internal     │
    ├──────────────────┼────────────┼───────────────┼──────────────┤
    │ FNV-1a           │ ~1 GB/s    │ Good          │ Legacy       │
    └──────────────────┴────────────┴───────────────┴──────────────┘
```

### 7.2 Double Hashing Technique

Instead of k independent hash functions, use only 2 and derive k:

```
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║    gᵢ(x) = h₁(x) + i × h₂(x)  mod m,   for i = 0..k-1     ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝

    Example with MurmurHash3 (128-bit output):
      hash = MurmurHash3_128(x)
      h₁ = lower 64 bits of hash
      h₂ = upper 64 bits of hash

      position[0] = h₁ mod m
      position[1] = (h₁ + h₂) mod m
      position[2] = (h₁ + 2×h₂) mod m
      ...
      position[i] = (h₁ + i×h₂) mod m

    Proven: This produces no increase in FP rate compared to
    k truly independent hash functions (Kirsch & Mitzenmacher, 2006)
    
    Benefit: Only ONE hash computation regardless of k value
```

### 7.3 Memory-Mapped Bloom Filters

```
    For very large filters that exceed available RAM:

    ┌─────────────────────────────────────────────────────────┐
    │  File on disk: filter.bloom (2 GB)                       │
    │                                                          │
    │  mmap(fd, 2GB, PROT_READ, MAP_PRIVATE)                  │
    │       │                                                  │
    │       ▼                                                  │
    │  ┌────────────────────────────────────────┐             │
    │  │     Virtual Address Space              │             │
    │  │     OS pages in/out as needed          │             │
    │  │     Hot portions stay in page cache    │             │
    │  └────────────────────────────────────────┘             │
    │                                                          │
    │  Advantages:                                             │
    │  - No explicit memory management                         │
    │  - OS handles caching based on access patterns           │
    │  - Multiple processes can share same physical pages      │
    │  - Startup time: O(1) — no need to read entire file      │
    └─────────────────────────────────────────────────────────┘
```

### 7.4 Serialization for Network Transfer

```
    Compact wire format:

    ┌────────┬────────┬─────────┬───────────────────────┐
    │ Header │ m (u64)│ k (u8)  │ Bit array (m/8 bytes) │
    │ 4 bytes│ 8 bytes│ 1 byte  │ variable              │
    └────────┴────────┴─────────┴───────────────────────┘

    Optimization: Compress before sending (bit arrays compress well
    when sparsely or densely populated — worst case at 50% fill)
    
    Common formats:
    - Raw bytes (simplest, used in Cassandra gossip)
    - Protocol Buffers wrapped (used in gRPC services)
    - Snappy/LZ4 compressed (for large filters over WAN)
```

---

## 8. Operational Concerns

### 8.1 Monitoring FP Rate in Production

```
    Measure actual FP rate (it may drift from theoretical):

    actual_fp_rate = false_positives / (false_positives + true_negatives)

    Track:
    - bloom_filter_true_positive_count   (BF said yes, item exists)
    - bloom_filter_false_positive_count  (BF said yes, item doesn't exist)
    - bloom_filter_true_negative_count   (BF said no, item doesn't exist)
    
    Alert when: actual_fp > 2 × configured_fp_threshold
    
    Cassandra exposes: bloom-filter-off-heap-memory-used
                       bloom-filter-false-ratio (per table)
```

### 8.2 When to Rebuild/Resize

```
    Rebuild when:
    1. Actual FP rate exceeds threshold (filter is overfull)
    2. After major deletions (if using counting variant)
    3. After compaction (merge filters of merged SSTables)

    Signs of an overfull filter:
    - n_actual >> n_designed → FP rate increases exponentially
    - Bit saturation > 60% → past optimal operating point

    ┌────────────────────────────────────────────────┐
    │  Fill ratio vs FP rate (k=7, designed for 1%)  │
    │                                                 │
    │  Fill %  │  Actual FP Rate                      │
    │  ────────┼───────────────                       │
    │   50%    │  1.0% (optimal)                      │
    │   60%    │  3.2%                                │
    │   70%    │  8.2%                                │
    │   80%    │  17.5%                               │
    │   90%    │  34.8%                               │
    │   95%    │  51.2%                               │
    └────────────────────────────────────────────────┘
```

### 8.3 Memory Budget Planning

```
    Budget formula:
    
    memory_bytes = n × bits_per_element / 8

    ┌─────────────────────────────────────────────────────────────┐
    │  Planning Table: Memory per million elements                  │
    │                                                              │
    │  FP Rate │ Bits/elem │ Per 1M elems │ Per 1B elems          │
    │  ────────┼───────────┼──────────────┼─────────────          │
    │  10%     │  4.79     │  0.57 MB     │  570 MB               │
    │  1%      │  9.58     │  1.14 MB     │  1.14 GB              │
    │  0.1%    │  14.37    │  1.71 MB     │  1.71 GB              │
    │  0.01%   │  19.17    │  2.28 MB     │  2.28 GB              │
    └─────────────────────────────────────────────────────────────┘

    Rule of thumb: Each 10× reduction in FP costs ~4.8 extra bits/element
    (i.e., ~0.6 MB per million elements per decade of FP reduction)
```

---

## 9. Architect's Decision Framework

### When to Use a Bloom Filter

```
    ╔═══════════════════════════════════════════════════════════════════╗
    ║  USE A BLOOM FILTER WHEN:                                        ║
    ║                                                                   ║
    ║  ✓ You need to answer "is X in set S?" frequently                ║
    ║  ✓ The set S is too large to store entirely in memory             ║
    ║  ✓ False positives are tolerable (you can verify elsewhere)       ║
    ║  ✓ False negatives are NOT tolerable                              ║
    ║  ✓ The set is relatively static (or you can afford rebuilds)      ║
    ║  ✓ You want to avoid expensive I/O or network calls               ║
    ║                                                                   ║
    ║  DO NOT USE WHEN:                                                 ║
    ║                                                                   ║
    ║  ✗ You need to enumerate/retrieve elements                        ║
    ║  ✗ You need exact answers (zero tolerance for FP)                 ║
    ║  ✗ You need frequent deletions (use Cuckoo/Counting instead)      ║
    ║  ✗ The set is small enough to fit in a hash set                   ║
    ║  ✗ FP cost is very high (e.g., security-critical access control)  ║
    ╚═══════════════════════════════════════════════════════════════════╝
```

### Decision Tree

```
    Need membership testing?
    │
    ├── Set fits in memory as hash set? → Use HashSet (exact, simple)
    │
    ├── Need to retrieve elements? → Use Hash Table or B-Tree
    │
    ├── Need deletion support?
    │   ├── High load factor (>95%)? → Cuckoo Filter
    │   ├── Need merging? → Quotient Filter
    │   └── Simple deletion? → Counting Bloom Filter
    │
    ├── Static dataset (build once, query many)?
    │   ├── Space is premium? → Ribbon Filter (RocksDB)
    │   └── Otherwise → Standard Bloom Filter
    │
    ├── Unknown/growing n?  → Scalable Bloom Filter
    │
    └── CPU-bound (many queries/sec)?
        ├── Blocked Bloom Filter (cache-line optimized)
        └── Or Cuckoo Filter (good locality)
```

### Cost-Benefit Analysis Template

```
    Scenario: [Your use case]
    
    Without Bloom Filter:
      - Queries/sec: Q
      - Cost per unnecessary check: C (ms or $)
      - Negative query ratio: R (typically 90-99%)
      - Wasted work: Q × R × C

    With Bloom Filter:
      - Memory cost: n × bits_per_elem / 8
      - Remaining wasted work: Q × R × FP_rate × C
      - Savings: Q × R × (1 - FP_rate) × C
    
    Example (Cassandra-like):
      Q = 100,000 queries/sec
      R = 95% are misses on a given SSTable
      C = 5ms (disk seek)
      
      Without BF: 100K × 0.95 × 5ms = 475,000 ms of wasted I/O/sec
      With BF (1% FP): 100K × 0.95 × 0.01 × 5ms = 4,750 ms wasted
      
      Savings: 99% reduction in unnecessary disk I/O
      Cost: ~1.14 MB per million keys in the SSTable
```

---

## Summary

| Aspect | Key Takeaway |
|--------|-------------|
| Space | ~10 bits/element for 1% FP — 10-50× smaller than hash sets |
| Speed | O(k) hash computations, typically k ≤ 10 |
| Guarantee | Zero false negatives, configurable false positives |
| Best for | Guarding expensive operations (disk, network, computation) |
| Worst for | Small sets, deletion-heavy workloads, exact requirements |
| Production | Cassandra, RocksDB, Chrome, Bitcoin, CDNs — everywhere |
