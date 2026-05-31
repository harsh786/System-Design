# Segment Tree Patterns

## Decision Flowchart

```
Need range queries on mutable array?
├── Point update + Range query?
│   ├── Only prefix sums / point query? → BIT (Fenwick Tree)
│   ├── Range min/max (static)? → Sparse Table O(1) query
│   └── General associative op? → Segment Tree
├── Range update + Range query? → Segment Tree + Lazy Propagation
├── Need versioning / historical queries? → Persistent Segment Tree
├── Range too large (1e9+)? → Dynamic / Coordinate-Compressed Segment Tree
└── Need order statistics in range? → Merge Sort Tree or Persistent Seg Tree
```

## When to Use What: Decision Table

| Feature | BIT (Fenwick) | Sparse Table | Segment Tree |
|---------|--------------|--------------|--------------|
| Point update | O(log n) | Not supported | O(log n) |
| Range query | O(log n) | O(1) | O(log n) |
| Range update | O(log n) with trick | Not supported | O(log n) with lazy |
| Space | O(n) | O(n log n) | O(4n) |
| Code complexity | Simple | Simple | Moderate |
| Supports min/max | No (only invertible ops) | Yes (static) | Yes |
| Supports lazy prop | No | No | Yes |
| Persistence | Hard | N/A | Natural |
| Best for | Sum/XOR, simple cases | Static RMQ | Everything else |

**Rule of thumb**: Use BIT if you can. Use Sparse Table for static RMQ. Use Segment Tree for everything else.

---

## Tree Structure Visualization

```
Array: [2, 1, 5, 3, 4, 7, 2, 6]  (indices 0..7)

Segment Tree (Sum) stored in tree[1..15]:

                    [30]                    tree[1] → range [0,7]
                  /      \
              [11]        [19]              tree[2]=[0,3], tree[3]=[4,7]
             /    \      /    \
          [3]    [8]  [11]   [8]            tree[4]=[0,1], tree[5]=[2,3]...
         / \    / \   / \   / \
        2   1  5   3 4   7 2   6            tree[8..15] = leaves

Index mapping:
- Root = 1
- Left child of i = 2*i
- Right child of i = 2*i + 1
- Parent of i = i / 2
- Leaves start at index n (for n = power of 2)
```

---

## Iterative vs Recursive Comparison

| Aspect | Recursive | Iterative |
|--------|-----------|-----------|
| Code length | Longer | Shorter |
| Cache performance | Worse (top-down) | Better (bottom-up) |
| Lazy propagation | Natural | Complex |
| Persistent tree | Natural | Very hard |
| Constant factor | Higher | Lower (~2x faster) |
| Debugging | Easier | Harder |
| Flexibility | More (merge sort tree etc) | Less |

**Recommendation**: Use iterative for competitive programming speed. Use recursive for interviews (clearer logic) and when you need lazy propagation or persistence.

---

## Pattern 1: Basic Segment Tree (Range Sum + Point Update)

### Signal
- Array is mutable (point updates)
- Need range sum/product/XOR queries
- Multiple queries intermixed with updates

### Template (Java) — Recursive

```java
class SegmentTree {
    int[] tree;
    int n;

    // Build: O(n)
    public SegmentTree(int[] nums) {
        n = nums.length;
        tree = new int[4 * n];  // safe size
        build(nums, 1, 0, n - 1);
    }

    private void build(int[] nums, int node, int start, int end) {
        if (start == end) {
            tree[node] = nums[start];
            return;
        }
        int mid = (start + end) / 2;
        build(nums, 2 * node, start, mid);
        build(nums, 2 * node + 1, mid + 1, end);
        tree[node] = tree[2 * node] + tree[2 * node + 1];  // merge
    }

    // Point Update: O(log n)
    public void update(int idx, int val) {
        update(1, 0, n - 1, idx, val);
    }

    private void update(int node, int start, int end, int idx, int val) {
        if (start == end) {
            tree[node] = val;
            return;
        }
        int mid = (start + end) / 2;
        if (idx <= mid) update(2 * node, start, mid, idx, val);
        else update(2 * node + 1, mid + 1, end, idx, val);
        tree[node] = tree[2 * node] + tree[2 * node + 1];
    }

    // Range Query: O(log n)
    public int query(int l, int r) {
        return query(1, 0, n - 1, l, r);
    }

    private int query(int node, int start, int end, int l, int r) {
        if (r < start || end < l) return 0;          // no overlap
        if (l <= start && end <= r) return tree[node]; // total overlap
        int mid = (start + end) / 2;                   // partial overlap
        return query(2 * node, start, mid, l, r)
             + query(2 * node + 1, mid + 1, end, l, r);
    }
}
```

### Template (Java) — Iterative (Bottom-Up)

```java
class SegmentTreeIterative {
    int[] tree;
    int n;

    public SegmentTreeIterative(int[] nums) {
        n = nums.length;
        tree = new int[2 * n];
        // Build leaves
        for (int i = 0; i < n; i++) tree[n + i] = nums[i];
        // Build internal nodes
        for (int i = n - 1; i > 0; i--) tree[i] = tree[2*i] + tree[2*i+1];
    }

    // Point update: O(log n)
    public void update(int idx, int val) {
        idx += n;
        tree[idx] = val;
        while (idx > 1) {
            idx /= 2;
            tree[idx] = tree[2*idx] + tree[2*idx+1];
        }
    }

    // Range query [l, r): O(log n)
    public int query(int l, int r) {
        int sum = 0;
        l += n; r += n;
        while (l < r) {
            if ((l & 1) == 1) sum += tree[l++];
            if ((r & 1) == 1) sum += tree[--r];
            l >>= 1; r >>= 1;
        }
        return sum;
    }
}
```

### Complexity
- Build: O(n)
- Update: O(log n)
- Query: O(log n)
- Space: O(n) — specifically 4n for recursive, 2n for iterative

---

## Pattern 2: Range Min/Max Query (RMQ)

### Signal
- Need minimum or maximum over arbitrary subarray
- Array is mutable (if static, prefer Sparse Table for O(1) query)

### Template (Java)

```java
class RMQSegmentTree {
    int[] tree;
    int n;

    public RMQSegmentTree(int[] nums) {
        n = nums.length;
        tree = new int[4 * n];
        Arrays.fill(tree, Integer.MAX_VALUE);
        build(nums, 1, 0, n - 1);
    }

    private void build(int[] nums, int node, int start, int end) {
        if (start == end) { tree[node] = nums[start]; return; }
        int mid = (start + end) / 2;
        build(nums, 2*node, start, mid);
        build(nums, 2*node+1, mid+1, end);
        tree[node] = Math.min(tree[2*node], tree[2*node+1]);
    }

    public void update(int idx, int val) { update(1, 0, n-1, idx, val); }

    private void update(int node, int start, int end, int idx, int val) {
        if (start == end) { tree[node] = val; return; }
        int mid = (start + end) / 2;
        if (idx <= mid) update(2*node, start, mid, idx, val);
        else update(2*node+1, mid+1, end, idx, val);
        tree[node] = Math.min(tree[2*node], tree[2*node+1]);
    }

    public int queryMin(int l, int r) { return queryMin(1, 0, n-1, l, r); }

    private int queryMin(int node, int start, int end, int l, int r) {
        if (r < start || end < l) return Integer.MAX_VALUE;
        if (l <= start && end <= r) return tree[node];
        int mid = (start + end) / 2;
        return Math.min(queryMin(2*node, start, mid, l, r),
                        queryMin(2*node+1, mid+1, end, l, r));
    }
}
```

### Complexity
Same as basic segment tree: O(n) build, O(log n) update/query.

---

## Pattern 3: Lazy Propagation (Range Update + Range Query)

### Signal
- **Range updates** (add value to all elements in [l, r])
- Combined with **range queries**
- Without lazy: range update is O(n). With lazy: O(log n)

### Core Idea

```
Lazy = "I haven't pushed this update to my children yet"

When updating a range:
  - If current node fully covered → update this node, store pending in lazy[]
  - Don't recurse further (that's the optimization)

When querying or updating and passing through a node with pending lazy:
  - Push lazy down to children before proceeding
```

### Step-by-Step Trace

```
Array: [1, 3, 5, 7, 9]    Operation: add 3 to range [1, 3]

Before:
tree[1]=25 [0,4]         lazy[1]=0
├── tree[2]=9 [0,1]      lazy[2]=0
│   ├── tree[4]=1 [0,0]
│   └── tree[5]=3 [1,1]
└── tree[3]=16 [2,4]     lazy[3]=0
    ├── tree[6]=12 [2,3]
    │   ├── tree[12]=5
    │   └── tree[13]=7
    └── tree[7]=9 [4,4]

Step 1: update(node=1, [0,4], l=1, r=3)
  Partial overlap → push down (nothing to push), recurse both

Step 2: update(node=2, [0,1], l=1, r=3)
  Partial overlap → recurse
  - update(node=5, [1,1], l=1, r=3): FULL overlap
    tree[5] += 3*1 = 6, lazy[5] += 3 (leaf, no children to defer)
  - tree[2] = tree[4] + tree[5] = 1 + 6 = 7

Step 3: update(node=3, [2,4], l=1, r=3)
  Partial overlap → recurse
  - update(node=6, [2,3], l=1, r=3): FULL overlap!
    tree[6] += 3*2 = 18, lazy[6] += 3    ← STOP HERE, don't go deeper
  - tree[7] unchanged
  - tree[3] = tree[6] + tree[7] = 18 + 9 = 27

After:
tree[1]=34 [0,4]         lazy[1]=0
├── tree[2]=7 [0,1]      lazy[2]=0
│   ├── tree[4]=1 [0,0]
│   └── tree[5]=6 [1,1]
└── tree[3]=27 [2,4]     lazy[3]=0
    ├── tree[6]=18 [2,3]  lazy[6]=3  ← PENDING! children not yet updated
    └── tree[7]=9 [4,4]

If we later query [2,2], we'd push lazy[6]=3 down to children first.
```

### Template (Java) — Range Add + Range Sum

```java
class LazySegmentTree {
    long[] tree, lazy;
    int n;

    public LazySegmentTree(int[] nums) {
        n = nums.length;
        tree = new long[4 * n];
        lazy = new long[4 * n];
        build(nums, 1, 0, n - 1);
    }

    private void build(int[] nums, int node, int start, int end) {
        if (start == end) { tree[node] = nums[start]; return; }
        int mid = (start + end) / 2;
        build(nums, 2*node, start, mid);
        build(nums, 2*node+1, mid+1, end);
        tree[node] = tree[2*node] + tree[2*node+1];
    }

    private void pushDown(int node, int start, int end) {
        if (lazy[node] != 0) {
            int mid = (start + end) / 2;
            // Apply to left child
            tree[2*node] += lazy[node] * (mid - start + 1);
            lazy[2*node] += lazy[node];
            // Apply to right child
            tree[2*node+1] += lazy[node] * (end - mid);
            lazy[2*node+1] += lazy[node];
            // Clear
            lazy[node] = 0;
        }
    }

    // Range Update: add val to all elements in [l, r]
    public void update(int l, int r, long val) {
        update(1, 0, n-1, l, r, val);
    }

    private void update(int node, int start, int end, int l, int r, long val) {
        if (r < start || end < l) return;              // no overlap
        if (l <= start && end <= r) {                  // total overlap
            tree[node] += val * (end - start + 1);
            lazy[node] += val;
            return;
        }
        pushDown(node, start, end);                    // partial overlap
        int mid = (start + end) / 2;
        update(2*node, start, mid, l, r, val);
        update(2*node+1, mid+1, end, l, r, val);
        tree[node] = tree[2*node] + tree[2*node+1];
    }

    // Range Query: sum of [l, r]
    public long query(int l, int r) {
        return query(1, 0, n-1, l, r);
    }

    private long query(int node, int start, int end, int l, int r) {
        if (r < start || end < l) return 0;
        if (l <= start && end <= r) return tree[node];
        pushDown(node, start, end);
        int mid = (start + end) / 2;
        return query(2*node, start, mid, l, r)
             + query(2*node+1, mid+1, end, l, r);
    }
}
```

### Variants of Lazy Propagation

| Operation | tree[node] update | lazy propagation |
|-----------|------------------|-----------------|
| Range add, query sum | `tree += val * len` | `lazy += val` |
| Range set, query sum | `tree = val * len` | `lazy = val` (use sentinel) |
| Range add, query min | `tree += val` | `lazy += val` |
| Range set, query min | `tree = val` | `lazy = val` |
| Range multiply + add | Use two lazy values (mul, add) | Compose carefully |

### Complexity
- Build: O(n)
- Range Update: O(log n)
- Range Query: O(log n)
- Space: O(n)

---

## Pattern 4: Segment Tree with Merge Sort (Count Smaller After Self)

### Signal
- Need to count elements satisfying condition in subarray
- "Count of smaller/greater numbers in range"
- Need order statistics without full persistence

### Approach
Each node stores the **sorted subarray** for its range. Query by binary searching at each visited node.

### Template (Java) — LC 315: Count of Smaller Numbers After Self

```java
class Solution {
    int[][] tree; // tree[node] = sorted elements in that range
    int n;

    public List<Integer> countSmaller(int[] nums) {
        n = nums.length;
        tree = new int[4 * n][];
        build(nums, 1, 0, n - 1);

        Integer[] result = new Integer[n];
        for (int i = 0; i < n; i++) {
            result[i] = query(1, 0, n-1, i+1, n-1, nums[i]);
        }
        return Arrays.asList(result);
    }

    private void build(int[] nums, int node, int start, int end) {
        if (start == end) {
            tree[node] = new int[]{nums[start]};
            return;
        }
        int mid = (start + end) / 2;
        build(nums, 2*node, start, mid);
        build(nums, 2*node+1, mid+1, end);
        tree[node] = merge(tree[2*node], tree[2*node+1]);
    }

    private int[] merge(int[] a, int[] b) {
        int[] res = new int[a.length + b.length];
        int i = 0, j = 0, k = 0;
        while (i < a.length && j < b.length)
            res[k++] = a[i] <= b[j] ? a[i++] : b[j++];
        while (i < a.length) res[k++] = a[i++];
        while (j < b.length) res[k++] = b[j++];
        return res;
    }

    // Count elements < val in range [l, r]
    private int query(int node, int start, int end, int l, int r, int val) {
        if (r < start || end < l) return 0;
        if (l <= start && end <= r) {
            // Binary search: count elements < val
            return lowerBound(tree[node], val);
        }
        int mid = (start + end) / 2;
        return query(2*node, start, mid, l, r, val)
             + query(2*node+1, mid+1, end, l, r, val);
    }

    private int lowerBound(int[] arr, int val) {
        int lo = 0, hi = arr.length;
        while (lo < hi) {
            int mid = (lo + hi) / 2;
            if (arr[mid] < val) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }
}
```

### Complexity
- Build: O(n log n)
- Query: O(log² n) per query
- Space: O(n log n)

---

## Pattern 5: Dynamic Segment Tree (Large Ranges)

### Signal
- Range is huge (e.g., [0, 1e9]) but operations are sparse
- Can't allocate 4*n array
- Two approaches: coordinate compression or pointer-based nodes

### Template (Java) — Pointer-Based Dynamic Segment Tree

```java
class DynamicSegTree {
    static int[] left, right;  // child pointers
    static long[] tree, lazy;
    static int cnt = 1;        // node counter (root = 1)
    static final int MAXNODES = 400000; // ~20 * number of operations

    static {
        left = new int[MAXNODES];
        right = new int[MAXNODES];
        tree = new long[MAXNODES];
        lazy = new long[MAXNODES];
    }

    static int newNode() { return ++cnt; }

    static void pushDown(int node, int start, int end) {
        if (left[node] == 0) left[node] = newNode();
        if (right[node] == 0) right[node] = newNode();
        if (lazy[node] != 0) {
            int mid = (start + end) / 2;
            tree[left[node]] += lazy[node] * (mid - start + 1);
            lazy[left[node]] += lazy[node];
            tree[right[node]] += lazy[node] * (end - mid);
            lazy[right[node]] += lazy[node];
            lazy[node] = 0;
        }
    }

    // Range update [l, r] += val on range [start, end]
    static void update(int node, int start, int end, int l, int r, long val) {
        if (r < start || end < l) return;
        if (l <= start && end <= r) {
            tree[node] += val * (end - start + 1);
            lazy[node] += val;
            return;
        }
        pushDown(node, start, end);
        int mid = (start + end) / 2;
        if (left[node] == 0) left[node] = newNode();
        if (right[node] == 0) right[node] = newNode();
        update(left[node], start, mid, l, r, val);
        update(right[node], mid+1, end, l, r, val);
        tree[node] = tree[left[node]] + tree[right[node]];
    }

    // Range query [l, r]
    static long query(int node, int start, int end, int l, int r) {
        if (node == 0 || r < start || end < l) return 0;
        if (l <= start && end <= r) return tree[node];
        pushDown(node, start, end);
        int mid = (start + end) / 2;
        return query(left[node], start, mid, l, r)
             + query(right[node], mid+1, end, l, r);
    }

    // Usage: update(1, 0, 1_000_000_000, l, r, val)
    //        query(1, 0, 1_000_000_000, l, r)
}
```

### Coordinate Compression Alternative

```java
// When all query/update positions are known in advance:
// 1. Collect all relevant coordinates
// 2. Sort and deduplicate
// 3. Map to [0, m-1] where m = unique coordinates
// 4. Build normal segment tree of size m

TreeSet<Integer> coords = new TreeSet<>();
// ... add all l, r, points ...
int[] sorted = coords.stream().mapToInt(Integer::intValue).toArray();
Map<Integer, Integer> compress = new HashMap<>();
for (int i = 0; i < sorted.length; i++) compress.put(sorted[i], i);
// Now use compress.get(x) as index into segment tree of size sorted.length
```

### Complexity
- Each operation creates at most O(log R) nodes (R = range size)
- Space: O(Q log R) where Q = number of operations
- Time: O(log R) per operation

---

## Pattern 6: Persistent Segment Tree

### Signal
- Need to access **historical versions** of the tree
- "Kth smallest in range [l, r]" — classic application
- Immutable updates: each update creates a new root, reuses unchanged subtrees

### Visualization

```
Version 0 (initial):        Version 1 (update idx=2):

      [A]                         [A']
     /   \                       /    \
   [B]   [C]                   [B]   [C']    ← only path to updated
   / \   / \                   / \   /  \      leaf is copied
  d   e f   g                 d   e f'   g

Nodes B, d, e, g are SHARED between versions.
Only A→A', C→C', f→f' are new allocations.
```

### Template (Java) — Kth Smallest in Range

```java
class PersistentSegTree {
    static final int MAXNODES = 20_000_000;
    static int[] left = new int[MAXNODES];
    static int[] right = new int[MAXNODES];
    static int[] sum = new int[MAXNODES];  // count of elements in range
    static int cnt = 0;

    static int newNode() { return ++cnt; }

    static int build(int start, int end) {
        int node = newNode();
        sum[node] = 0;
        if (start == end) return node;
        int mid = (start + end) / 2;
        left[node] = build(start, mid);
        right[node] = build(mid+1, end);
        return node;
    }

    // Insert value 'val' into tree rooted at 'prev', return new root
    static int update(int prev, int start, int end, int val) {
        int node = newNode();
        left[node] = left[prev];
        right[node] = right[prev];
        sum[node] = sum[prev] + 1;
        if (start == end) return node;
        int mid = (start + end) / 2;
        if (val <= mid)
            left[node] = update(left[prev], start, mid, val);
        else
            right[node] = update(right[prev], mid+1, end, val);
        return node;
    }

    // Query kth smallest between versions [root_l-1] and [root_r]
    static int query(int nodeL, int nodeR, int start, int end, int k) {
        if (start == end) return start;
        int mid = (start + end) / 2;
        int leftCount = sum[left[nodeR]] - sum[left[nodeL]];
        if (k <= leftCount)
            return query(left[nodeL], left[nodeR], start, mid, k);
        else
            return query(right[nodeL], right[nodeR], mid+1, end, k - leftCount);
    }

    // Usage for "Kth Smallest Element in Range [l, r]":
    // 1. Coordinate compress values to [0, m-1]
    // 2. Build version 0 (empty tree over [0, m-1])
    // 3. For each element nums[i], create version[i+1] = update(version[i], ..., compressed[i])
    // 4. Query: query(version[l], version[r+1], 0, m-1, k) → get compressed index → map back
}
```

### Full Usage Example

```java
public int kthSmallest(int[] nums, int[][] queries) {
    // queries[i] = [l, r, k]
    int n = nums.length;

    // Coordinate compression
    int[] sorted = nums.clone();
    Arrays.sort(sorted);
    sorted = Arrays.stream(sorted).distinct().toArray();
    int m = sorted.length;
    Map<Integer, Integer> rank = new HashMap<>();
    for (int i = 0; i < m; i++) rank.put(sorted[i], i);

    // Build persistent segment tree
    int[] roots = new int[n + 1];
    roots[0] = PersistentSegTree.build(0, m - 1);
    for (int i = 0; i < n; i++) {
        roots[i+1] = PersistentSegTree.update(roots[i], 0, m-1, rank.get(nums[i]));
    }

    // Answer queries
    // kth smallest in nums[l..r]:
    // int compressedIdx = PersistentSegTree.query(roots[l], roots[r+1], 0, m-1, k);
    // int answer = sorted[compressedIdx];
}
```

### Complexity
- Build: O(n log m)
- Each update: O(log m) time, O(log m) new nodes
- Each query: O(log m)
- Space: O(n log m) total

---

## Pattern 7: Segment Tree Applications

### 7.1 Count Inversions

**Problem**: Count pairs (i, j) where i < j but nums[i] > nums[j].

```java
// Approach: Process right to left (or left to right), 
// use segment tree over value range to count elements already seen
// that are smaller/larger.

public long countInversions(int[] nums) {
    // Coordinate compress
    int[] sorted = nums.clone();
    Arrays.sort(sorted);
    Map<Integer, Integer> rank = new HashMap<>();
    int r = 0;
    for (int v : sorted) if (!rank.containsKey(v)) rank.put(v, r++);
    int m = r;

    // Segment tree over values [0, m-1], counts
    int[] tree = new int[4 * m];
    long inversions = 0;

    // Process left to right: for each element, count how many
    // already-inserted elements are GREATER (query [rank+1, m-1])
    for (int num : nums) {
        int idx = rank.get(num);
        inversions += query(tree, 1, 0, m-1, idx+1, m-1);
        update(tree, 1, 0, m-1, idx);
    }
    return inversions;
}
// (query and update are standard range-sum and point-add-1)
```

### 7.2 Rectangle Area (Sweep Line + Segment Tree)

**Problem**: LC 850 — Find total area covered by rectangles (handling overlaps).

```
Approach:
1. Sweep a vertical line from left to right
2. Events: rectangle starts (add y-interval) or ends (remove y-interval)
3. Segment tree tracks: "covered length" of y-axis at current x

Each node stores:
- cnt: how many rectangles fully cover this y-segment
- coveredLen: total length of y covered in this range
```

```java
class Solution {
    int[] cnt;        // count of full covers
    long[] covered;   // covered length
    int[] ys;         // compressed y-coordinates

    public int rectangleArea(int[][] rectangles) {
        // Collect and compress y-coordinates
        TreeSet<Integer> ySet = new TreeSet<>();
        List<int[]> events = new ArrayList<>();  // [x, type, y1, y2]

        for (int[] r : rectangles) {
            ySet.add(r[1]); ySet.add(r[3]);
            events.add(new int[]{r[0], 1, r[1], r[3]});   // open
            events.add(new int[]{r[2], -1, r[1], r[3]});  // close
        }
        events.sort((a,b) -> a[0] != b[0] ? a[0]-b[0] : a[1]-b[1]);
        ys = ySet.stream().mapToInt(Integer::intValue).toArray();
        int m = ys.length - 1;  // number of y-segments

        cnt = new int[4 * m];
        covered = new long[4 * m];

        long MOD = 1_000_000_007, ans = 0;
        int prevX = events.get(0)[0];

        for (int[] e : events) {
            int x = e[0];
            ans = (ans + covered[1] % MOD * ((x - prevX) % MOD)) % MOD;
            prevX = x;

            int lo = Arrays.binarySearch(ys, e[2]);
            int hi = Arrays.binarySearch(ys, e[3]) - 1;
            update(1, 0, m-1, lo, hi, e[1]);
        }
        return (int)(ans % MOD);
    }

    void update(int node, int start, int end, int l, int r, int val) {
        if (r < start || end < l) return;
        if (l <= start && end <= r) {
            cnt[node] += val;
        } else {
            int mid = (start + end) / 2;
            update(2*node, start, mid, l, r, val);
            update(2*node+1, mid+1, end, l, r, val);
        }
        // Recompute covered length
        if (cnt[node] > 0) {
            covered[node] = ys[end+1] - ys[start];
        } else if (start == end) {
            covered[node] = 0;
        } else {
            covered[node] = covered[2*node] + covered[2*node+1];
        }
    }
}
```

### 7.3 Falling Squares (LC 699)

**Problem**: Squares fall on x-axis. Each lands on highest point in its x-range. Return max heights after each drop.

```java
// Approach: For each square at [left, left+side-1] with height side:
// 1. Query max height in [left, left+side-1]
// 2. New height = queryMax + side
// 3. Range update: set [left, left+side-1] to newHeight
// 4. Answer = running max of all heights

// Uses lazy segment tree with "range set" + "range max query"
// Coordinate compress x-values first since range can be up to 1e8
```

### 7.4 My Calendar I / II / III (LC 729, 731, 732)

**My Calendar III** — Find maximum overlap (booking count) at any point.

```java
class MyCalendarThree {
    // Dynamic segment tree with lazy propagation (range add, range max query)
    // Range: [0, 10^9] — use dynamic nodes
    Map<Integer, Integer> tree = new HashMap<>();
    Map<Integer, Integer> lazy = new HashMap<>();

    public int book(int start, int end) {
        update(1, 0, 1_000_000_000, start, end - 1, 1);
        return tree.getOrDefault(1, 0);
    }

    void update(int node, int s, int e, int l, int r, int val) {
        if (r < s || e < l) return;
        if (l <= s && e <= r) {
            tree.merge(node, val, Integer::sum);
            lazy.merge(node, val, Integer::sum);
            return;
        }
        int mid = (s + e) / 2;
        pushDown(node);
        update(2*node, s, mid, l, r, val);
        update(2*node+1, mid+1, e, l, r, val);
        tree.put(node, Math.max(tree.getOrDefault(2*node, 0),
                                tree.getOrDefault(2*node+1, 0)));
    }

    void pushDown(int node) {
        int lz = lazy.getOrDefault(node, 0);
        if (lz != 0) {
            tree.merge(2*node, lz, Integer::sum);
            lazy.merge(2*node, lz, Integer::sum);
            tree.merge(2*node+1, lz, Integer::sum);
            lazy.merge(2*node+1, lz, Integer::sum);
            lazy.put(node, 0);
        }
    }
}
```

**My Calendar I** — Simpler: just check if max in [start, end-1] is 0 before booking.

**My Calendar II** — Check if max in [start, end-1] < 2 before booking.

---

## Common Mistakes and Tips

1. **Array size**: Always allocate `4*n` for recursive tree (not `2*n`).
2. **Off-by-one**: Be consistent with inclusive `[l, r]` vs half-open `[l, r)`.
3. **Lazy push timing**: Always push down **before** recursing into children for queries or partial updates.
4. **Identity element**: Sum→0, Min→INT_MAX, Max→INT_MIN, GCD→0, OR→0, AND→all 1s.
5. **Merge function must be associative**: `merge(merge(a,b), c) == merge(a, merge(b,c))`.
6. **Coordinate compression**: When range is huge but events are sparse, compress first.

---

## LeetCode Problems by Pattern

| Problem | Pattern | Difficulty |
|---------|---------|-----------|
| 307. Range Sum Query - Mutable | Basic Segment Tree | Medium |
| 315. Count of Smaller Numbers After Self | Merge Sort Tree | Hard |
| 327. Count of Range Sum | Merge Sort / Seg Tree | Hard |
| 493. Reverse Pairs | Merge Sort / Seg Tree | Hard |
| 699. Falling Squares | Lazy (range set + max) | Hard |
| 715. Range Module | Lazy (interval tracking) | Hard |
| 729/731/732. My Calendar I/II/III | Dynamic + Lazy | Med/Med/Hard |
| 850. Rectangle Area II | Sweep Line + Seg Tree | Hard |
| 1157. Online Majority Element In Subarray | Merge Sort Tree | Hard |
| 2286. Booking Concert Tickets in Groups | Lazy + max/sum | Hard |

---

## Summary

```
Segment Tree = Divide array into O(n) nodes representing ranges
             + Combine children via any associative merge function
             + Answer range queries in O(log n) by visiting O(log n) nodes

Extensions:
  Lazy    → amortize range updates to O(log n)
  Persist → version control with path copying
  Dynamic → handle enormous ranges with sparse allocation
  Merge   → store sorted arrays for order statistics
```
