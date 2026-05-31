# Binary Indexed Tree (Fenwick Tree) Patterns

## Mental Model

A BIT is a **partial-sum tree** stored in a flat array where each index is responsible for a range of elements determined by its **lowest set bit**. It achieves O(log n) point update and prefix query with minimal code and constant factors far better than segment trees.

---

## How `lowbit` Works: `x & (-x)`

```
x      = 12 = 1100
-x     = ~x + 1 = 0011 + 1 = 0100
x & -x = 1100 & 0100 = 0100 = 4

x      = 6  = 0110
-x     =      1010
x & -x =      0010 = 2

x      = 7  = 0111
-x     =      1001
x & -x =      0001 = 1
```

**lowbit(x)** extracts the rightmost set bit. This determines:
- **Update**: which ancestors to propagate to (add lowbit)
- **Query**: which chunks to sum (subtract lowbit)

```
Index:    1    2    3    4    5    6    7    8
lowbit:   1    2    1    4    1    2    1    8
Range:   [1,1][1,2][3,3][1,4][5,5][5,6][7,7][1,8]
```

### Tree Structure Visualization

```
Level 3:  |_______________ bit[8] covers [1..8] _______________|
Level 2:  |____ bit[4] [1..4] ____|              |__ bit[6] [5..6] __|
Level 1:  | bit[2] [1..2] |       | bit[6] [5..6]|
Level 0:  bit[1]  bit[3]  bit[5]  bit[7]
           [1]     [3]     [5]     [7]
```

### Update Trace: update(3, +5) on n=8

```
i = 3 (011) → add lowbit(3)=1 → i=4 (100) → add lowbit(4)=4 → i=8 (1000) → done
Path: bit[3] += 5, bit[4] += 5, bit[8] += 5
```

### Query Trace: query(7) — prefix sum [1..7]

```
i = 7 (111) → sub lowbit(7)=1 → i=6 (110) → sub lowbit(6)=2 → i=4 (100) → sub lowbit(4)=4 → i=0 → done
Sum = bit[7] + bit[6] + bit[4]
    = a[7]   + a[5..6] + a[1..4]
```

---

## Decision Flowchart

```
Need range queries + updates?
├── Point update + Range query (prefix sums)?
│   ├── 1D? → Basic BIT (Pattern 1-2)
│   └── 2D? → 2D BIT (Pattern 5)
├── Range update + Point query?
│   └── BIT on difference array (Pattern 3)
├── Range update + Range query?
│   └── Two-BIT trick (Pattern 4)
├── Need order statistics / kth element?
│   └── BIT + Binary Lifting (Pattern 7)
├── Need inversion count / rank queries?
│   └── BIT + Coordinate Compression (Pattern 6, 8)
└── Need arbitrary range operations (min/max/gcd)?
    └── Use Segment Tree instead
```

---

## BIT vs Segment Tree

| Criteria | BIT | Segment Tree |
|----------|-----|--------------|
| Code complexity | ~15 lines | ~60 lines |
| Constant factor | Very small | 2-4x larger |
| Memory | n+1 array | 2n or 4n array |
| Point update + prefix query | O(log n) | O(log n) |
| Arbitrary range query [l,r] | Via prefix diff | Native |
| Range update + range query | Two BITs (tricky) | Lazy propagation |
| Min/Max/GCD queries | Not supported | Supported |
| Persistent version | Awkward | Natural |
| 2D extension | Simple | Complex (2D seg tree) |
| When to prefer | Prefix-sum problems, inversions, competitive programming | Complex operations, need full flexibility |

**Rule of thumb**: If the operation is **invertible** (sum, xor) and queries are prefix-based, use BIT. Otherwise, use segment tree.

---

## Pattern 1: Basic BIT — Point Update + Prefix Sum Query

### Signal
- Array with point updates
- Need prefix sum or range sum queries
- "Sum of elements in range [l, r]"

### Template

```java
class BIT {
    int[] tree;
    int n;

    BIT(int n) {
        this.n = n;
        this.tree = new int[n + 1]; // 1-indexed
    }

    // Build from array in O(n)
    BIT(int[] nums) {
        this.n = nums.length;
        this.tree = new int[n + 1];
        for (int i = 0; i < n; i++) tree[i + 1] = nums[i];
        for (int i = 1; i <= n; i++) {
            int parent = i + (i & -i);
            if (parent <= n) tree[parent] += tree[i];
        }
    }

    // Add delta to index i (1-indexed)
    void update(int i, int delta) {
        for (; i <= n; i += i & -i)
            tree[i] += delta;
    }

    // Prefix sum [1..i]
    int query(int i) {
        int sum = 0;
        for (; i > 0; i -= i & -i)
            sum += tree[i];
        return sum;
    }

    // Range sum [l..r] (1-indexed)
    int query(int l, int r) {
        return query(r) - query(l - 1);
    }
}
```

### Complexity
- **Update**: O(log n)
- **Query**: O(log n)
- **Build**: O(n) with propagation trick, O(n log n) naive
- **Space**: O(n)

---

## Pattern 2: Range Sum Query

### Signal
- "Sum of elements between index l and r"
- Multiple queries after updates

### Template

```java
// Uses Pattern 1 BIT directly
// rangeSum(l, r) = query(r) - query(l - 1)

// Example: nums = [1, 3, 5, 7, 9], find sum [2..4] (1-indexed)
// query(4) = 1+3+5+7 = 16
// query(1) = 1
// answer = 16 - 1 = 15

// LC 307: Range Sum Query - Mutable
class NumArray {
    BIT bit;
    int[] nums;

    NumArray(int[] nums) {
        this.nums = nums;
        bit = new BIT(nums); // O(n) build
    }

    void update(int index, int val) {
        int delta = val - nums[index];
        nums[index] = val;
        bit.update(index + 1, delta); // convert to 1-indexed
    }

    int sumRange(int left, int right) {
        return bit.query(right + 1) - bit.query(left); // 0-indexed input
    }
}
```

---

## Pattern 3: Range Update + Point Query

### Signal
- "Add val to all elements in [l, r]"
- "What is the value at index i?"
- Difference array technique

### Visualization

```
Difference array idea:
  To add +5 to range [2, 5]:
    diff[2] += 5
    diff[6] -= 5

  Value at index i = prefix_sum(diff, i)

  Using BIT on diff array:
    update(2, +5), update(6, -5) → O(log n) each
    query(i) gives point value       → O(log n)
```

### Template

```java
class RangeUpdatePointQuery {
    BIT bit;

    RangeUpdatePointQuery(int n) {
        bit = new BIT(n);
    }

    // Add val to all positions in [l, r] (1-indexed)
    void rangeUpdate(int l, int r, int val) {
        bit.update(l, val);
        bit.update(r + 1, -val);
    }

    // Get value at position i (1-indexed)
    int pointQuery(int i) {
        return bit.query(i); // prefix sum of difference array
    }
}
```

### Complexity
- **Range Update**: O(log n)
- **Point Query**: O(log n)

---

## Pattern 4: Range Update + Range Query

### Signal
- "Add val to all elements in [l, r]"
- "Sum of elements in [l, r]"
- Both operations needed together

### Derivation

```
Let diff[] be the difference array. Value at position i:
  a[i] = sum(diff[1..i])

Prefix sum of a[1..p]:
  sum(a[1..p]) = sum_{i=1}^{p} sum_{j=1}^{i} diff[j]
               = sum_{j=1}^{p} diff[j] * (p - j + 1)
               = (p+1) * sum(diff[1..p]) - sum(j * diff[j], j=1..p)

So we need two BITs:
  B1 stores diff[j]
  B2 stores j * diff[j]

  prefix_sum(p) = (p+1) * B1.query(p) - B2.query(p)
```

### Template

```java
class RangeUpdateRangeQuery {
    int n;
    BIT b1, b2; // b1 for diff[i], b2 for i*diff[i]

    RangeUpdateRangeQuery(int n) {
        this.n = n;
        b1 = new BIT(n);
        b2 = new BIT(n);
    }

    // Add val to [l, r]
    void rangeUpdate(int l, int r, long val) {
        // Update b1 (difference array)
        b1.update(l, val);
        b1.update(r + 1, -val);
        // Update b2 (i * difference array)
        b2.update(l, val * l);
        b2.update(r + 1, -val * (r + 1));
    }

    // Prefix sum [1..p]
    long prefixSum(int p) {
        return (long)(p + 1) * b1.query(p) - b2.query(p);
    }

    // Range sum [l..r]
    long rangeQuery(int l, int r) {
        return prefixSum(r) - prefixSum(l - 1);
    }
}
```

### Complexity
- **Range Update**: O(log n)
- **Range Query**: O(log n)
- **Space**: O(n) for two BITs

---

## Pattern 5: 2D BIT

### Signal
- 2D matrix with point updates
- "Sum of submatrix from (r1,c1) to (r2,c2)"
- LC 308: Range Sum Query 2D - Mutable

### Visualization

```
2D prefix sum with inclusion-exclusion:

sum(r2,c2) - sum(r1-1,c2) - sum(r2,c1-1) + sum(r1-1,c1-1)

    (r1-1,c1-1)────────(r1-1,c2)
         │    +             │  -
    (r2,c1-1)───────────(r2,c2)
         │  -              │ answer
```

### Template

```java
class BIT2D {
    int[][] tree;
    int rows, cols;

    BIT2D(int rows, int cols) {
        this.rows = rows;
        this.cols = cols;
        tree = new int[rows + 1][cols + 1];
    }

    void update(int r, int c, int delta) {
        for (int i = r; i <= rows; i += i & -i)
            for (int j = c; j <= cols; j += j & -j)
                tree[i][j] += delta;
    }

    // Prefix sum from (1,1) to (r,c)
    int query(int r, int c) {
        int sum = 0;
        for (int i = r; i > 0; i -= i & -i)
            for (int j = c; j > 0; j -= j & -j)
                sum += tree[i][j];
        return sum;
    }

    // Submatrix sum from (r1,c1) to (r2,c2)
    int query(int r1, int c1, int r2, int c2) {
        return query(r2, c2) - query(r1 - 1, c2)
             - query(r2, c1 - 1) + query(r1 - 1, c1 - 1);
    }
}
```

### Complexity
- **Update**: O(log(rows) * log(cols))
- **Query**: O(log(rows) * log(cols))
- **Space**: O(rows * cols)

---

## Pattern 6: BIT Applications — Counting Problems

### 6a. Count Inversions

**Signal**: Count pairs (i, j) where i < j but a[i] > a[j].

```java
// Traverse right to left. For each element, count how many
// smaller elements are already in the BIT (to its right).
// Or: traverse left to right, for each element count how many
// larger elements are already seen.

int countInversions(int[] nums) {
    int n = nums.length;
    // Coordinate compress
    int[] sorted = nums.clone();
    Arrays.sort(sorted);
    Map<Integer, Integer> rank = new HashMap<>();
    int r = 1;
    for (int v : sorted) rank.putIfAbsent(v, r++);

    BIT bit = new BIT(n);
    int inversions = 0;

    // Process left to right
    for (int i = 0; i < n; i++) {
        int pos = rank.get(nums[i]);
        // Count elements already inserted with rank > pos
        inversions += i - bit.query(pos); // i elements inserted, query(pos) are <= nums[i]
        bit.update(pos, 1);
    }
    return inversions;
}
```

### 6b. Count of Smaller Numbers After Self (LC 315)

**Signal**: For each element, count how many elements to its right are smaller.

```java
List<Integer> countSmaller(int[] nums) {
    int n = nums.length;
    // Coordinate compression
    int[] sorted = nums.clone();
    Arrays.sort(sorted);
    Map<Integer, Integer> rank = new HashMap<>();
    int r = 1;
    for (int v : sorted) rank.putIfAbsent(v, r++);

    BIT bit = new BIT(r);
    Integer[] result = new Integer[n];

    // Process RIGHT to LEFT
    for (int i = n - 1; i >= 0; i--) {
        int pos = rank.get(nums[i]);
        result[i] = bit.query(pos - 1); // count elements with rank < pos
        bit.update(pos, 1);
    }
    return Arrays.asList(result);
}
```

### 6c. Reverse Pairs (LC 493)

**Signal**: Count pairs (i, j) where i < j and nums[i] > 2 * nums[j].

```java
int reversePairs(int[] nums) {
    // Coordinate compress all values AND their doubles
    TreeSet<Long> set = new TreeSet<>();
    for (int x : nums) { set.add((long)x); set.add(2L * x); }
    Map<Long, Integer> rank = new HashMap<>();
    int r = 1;
    for (long v : set) rank.put(v, r++);

    BIT bit = new BIT(rank.size());
    int count = 0;

    // Process right to left
    for (int i = nums.length - 1; i >= 0; i--) {
        // Count elements already inserted with rank < rank(nums[i]) 
        // since those are values v where nums[i] > 2*v
        // Actually: we need nums[i] > 2*nums[j], so for current nums[i],
        // we query how many inserted have rank < rank_of(ceil(nums[i]/2) - epsilon)
        // Simpler: process left to right, for each j count i < j with nums[i] > 2*nums[j]
        count += bit.query(rank.size()) - bit.query(rank.get(2L * nums[i]));
        bit.update(rank.get((long)nums[i]), 1);
    }
    // Process left to right instead:
    // For each j, count already-inserted i with val > 2*nums[j]
    // = total_inserted - query(rank(2*nums[j]))
    return count;
}

// Cleaner left-to-right version:
int reversePairs2(int[] nums) {
    TreeSet<Long> set = new TreeSet<>();
    for (int x : nums) { set.add((long)x); set.add(2L * x); }
    Map<Long, Integer> rank = new HashMap<>();
    int r = 1;
    for (long v : set) rank.put(v, r++);

    int maxRank = rank.size();
    BIT bit = new BIT(maxRank);
    int count = 0;

    for (int i = 0; i < nums.length; i++) {
        // Count previously inserted elements > 2 * nums[i]
        int threshold = rank.get(2L * nums[i]);
        count += i - bit.query(threshold); // i elements inserted, query(threshold) are <= 2*nums[i]
        bit.update(rank.get((long)nums[i]), 1);
    }
    return count;
}
```

### 6d. Create Sorted Array through Instructions (LC 1649)

**Signal**: Insert elements one by one. Cost = min(elements_less_than, elements_greater_than).

```java
int createSortedArray(int[] instructions) {
    int MOD = 1_000_000_007;
    int max = 100_001; // constraint: values <= 10^5
    BIT bit = new BIT(max);
    long cost = 0;

    for (int i = 0; i < instructions.length; i++) {
        int val = instructions[i];
        int less = bit.query(val - 1);
        int greater = i - bit.query(val); // i elements inserted, query(val) are <= val
        cost = (cost + Math.min(less, greater)) % MOD;
        bit.update(val, 1);
    }
    return (int) cost;
}
```

---

## Pattern 7: Order Statistics with BIT — Kth Smallest via Binary Lifting

### Signal
- Maintain a multiset with insert/delete
- "Find kth smallest element"
- Alternative to order-statistics tree (policy-based in C++)

### Key Insight

BIT stores frequency. `query(x)` = count of elements <= x. To find kth smallest, we need the smallest x where `query(x) >= k`. Instead of binary searching over query (O(log^2 n)), we do **binary lifting on the BIT** in O(log n).

### Template

```java
// BIT stores frequencies. find(k) returns kth smallest in O(log n).
class OrderStatsBIT {
    int[] tree;
    int n;

    OrderStatsBIT(int n) {
        this.n = n;
        this.tree = new int[n + 1];
    }

    void update(int i, int delta) {
        for (; i <= n; i += i & -i)
            tree[i] += delta;
    }

    // Find kth smallest element (1-indexed k) in O(log n)
    // Returns the index (value after coord compression) of kth element
    int kth(int k) {
        int pos = 0;
        // Start from highest power of 2 <= n
        for (int pw = Integer.highestOneBit(n); pw > 0; pw >>= 1) {
            if (pos + pw <= n && tree[pos + pw] < k) {
                pos += pw;
                k -= tree[pos]; // subtract the count we've passed
            }
        }
        return pos + 1; // 1-indexed answer
    }
}

// Usage: maintain sorted multiset
// insert(val): bit.update(rank(val), 1)
// delete(val): bit.update(rank(val), -1)
// kth smallest: bit.kth(k) → gives rank, map back to value
```

### Trace: kth(5) on BIT of size 8

```
Frequencies: [0, 2, 1, 0, 3, 1, 0, 1, 0]  (indices 1-8)
Cumulative:  [0, 2, 3, 3, 6, 7, 7, 8, 8]

Finding 5th smallest:
  pw=8: pos+8=8, tree[8]=8 ≥ 5? Yes → skip
  pw=4: pos+4=4, tree[4]=6 ≥ 5? Yes → skip
  pw=2: pos+2=2, tree[2]=3 < 5? Yes → pos=2, k=5-3=2
  pw=1: pos+1=3, tree[3]=0 < 2? Yes → pos=3, k=2-0=2
  Wait, tree[3] in BIT is not cumulative — it stores partial sums.

Corrected: tree[] in BIT stores partial sums as per BIT structure.
  Built BIT from frequencies [2,1,0,3,1,0,1,0]:
  tree[1]=2, tree[2]=3, tree[3]=0, tree[4]=6, tree[5]=1, tree[6]=1, tree[7]=1, tree[8]=8

  pw=8: tree[8]=8, 8 < 5? No → skip
  pw=4: tree[4]=6, 6 < 5? No → skip
  pw=2: tree[2]=3, 3 < 5? Yes → pos=2, k=5-3=2
  pw=1: tree[3]=0, 0 < 2? Yes → pos=3, k=2-0=2
  → return pos+1 = 4. The 5th smallest is value at rank 4. ✓ (cumul[4]=6≥5, cumul[3]=3<5)
```

---

## Pattern 8: Coordinate Compression + BIT

### Signal
- Values up to 10^9 but array size up to 10^5
- Need to use values as BIT indices
- "Rank-based" queries

### Template

```java
// Compress values to ranks [1, n]
int[] coordinateCompress(int[] nums) {
    int[] sorted = nums.clone();
    Arrays.sort(sorted);
    // Remove duplicates and assign ranks
    Map<Integer, Integer> rank = new HashMap<>();
    int r = 1;
    for (int v : sorted) {
        if (!rank.containsKey(v)) rank.put(v, r++);
    }
    int[] compressed = new int[nums.length];
    for (int i = 0; i < nums.length; i++) {
        compressed[i] = rank.get(nums[i]);
    }
    return compressed;
    // BIT size = r (number of unique values)
}

// Alternative using Arrays + binary search (faster, no HashMap):
int compress(int val, int[] sorted) {
    return Arrays.binarySearch(sorted, val) + 1; // 1-indexed rank
}
```

### When to Use
- Values are too large for direct BIT indexing (e.g., up to 10^9)
- Only relative ordering matters (inversions, rank queries)
- Number of distinct values is manageable (typically <= 10^5)

### Full Example: Count Inversions with Coordinate Compression

```java
long countInversions(int[] nums) {
    int n = nums.length;
    int[] sorted = nums.clone();
    Arrays.sort(sorted);
    sorted = Arrays.stream(sorted).distinct().toArray(); // unique sorted values

    BIT bit = new BIT(sorted.length);
    long inversions = 0;

    for (int i = 0; i < n; i++) {
        int rank = Arrays.binarySearch(sorted, nums[i]) + 1;
        inversions += i - bit.query(rank); // elements seen so far with rank > current
        bit.update(rank, 1);
    }
    return inversions;
}
```

---

## Complete BIT Class Template (Java)

```java
class BIT {
    long[] tree;
    int n;

    BIT(int n) {
        this.n = n;
        tree = new long[n + 1];
    }

    // O(n) build from array
    BIT(int[] a) {
        n = a.length;
        tree = new long[n + 1];
        for (int i = 0; i < n; i++) tree[i + 1] = a[i];
        for (int i = 1; i <= n; i++) {
            int p = i + (i & -i);
            if (p <= n) tree[p] += tree[i];
        }
    }

    void update(int i, long delta) {
        for (; i <= n; i += i & -i) tree[i] += delta;
    }

    long query(int i) {
        long s = 0;
        for (; i > 0; i -= i & -i) s += tree[i];
        return s;
    }

    long query(int l, int r) {
        return query(r) - query(l - 1);
    }

    // Kth smallest (BIT stores frequencies)
    int kth(int k) {
        int pos = 0;
        for (int pw = Integer.highestOneBit(n); pw > 0; pw >>= 1) {
            if (pos + pw <= n && tree[pos + pw] < k) {
                pos += pw;
                k -= tree[pos];
            }
        }
        return pos + 1;
    }
}
```

---

## Summary Table

| Pattern | Update | Query | Use Case |
|---------|--------|-------|----------|
| Basic BIT | Point O(log n) | Prefix O(log n) | Range sums, frequency |
| Range Update + Point Query | Range O(log n) | Point O(log n) | Lazy point access |
| Range Update + Range Query | Range O(log n) | Range O(log n) | Full flexibility |
| 2D BIT | Point O(log^2) | Submatrix O(log^2) | Matrix sums |
| Order Stats BIT | Insert/Delete O(log n) | Kth O(log n) | Dynamic median, kth |
| Inversion Count | O(log n) per element | O(n log n) total | Sorting distance |

---

## LeetCode Problem Map

| Problem | Pattern | Key Idea |
|---------|---------|----------|
| 307. Range Sum Query Mutable | 1-2 | Basic BIT |
| 308. Range Sum Query 2D Mutable | 5 | 2D BIT |
| 315. Count of Smaller After Self | 6b + 8 | Right-to-left + compress |
| 327. Count of Range Sum | BIT + compress | Prefix sums as values |
| 493. Reverse Pairs | 6c + 8 | Include 2x in compression |
| 1649. Create Sorted Array | 6d | min(less, greater) |
| 2179. Count Good Triplets | BIT | Prefix frequency |
| 775. Global and Local Inversions | 6a | Inversion counting |
