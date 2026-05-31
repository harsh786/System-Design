# Advanced Patterns - Segment Tree, BIT, Bit Manipulation, Design, Concurrency, Prefix Sum, Sweep Line

---

# SEGMENT TREE / BINARY INDEXED TREE (BIT)

## When to Use

| Need | Best Structure |
|------|---------------|
| Point update + Range sum query | BIT (simpler) |
| Point update + Range min/max | Segment Tree |
| Range update + Range query | Segment Tree + Lazy Propagation |
| Count inversions / smaller after self | BIT |

## Segment Tree Template
```java
int[] tree;
int n;

void build(int[] arr) {
    n = arr.length;
    tree = new int[4 * n];
    build(arr, 1, 0, n - 1);
}

void build(int[] arr, int node, int start, int end) {
    if (start == end) { tree[node] = arr[start]; return; }
    int mid = (start + end) / 2;
    build(arr, 2*node, start, mid);
    build(arr, 2*node+1, mid+1, end);
    tree[node] = tree[2*node] + tree[2*node+1];  // merge
}

int query(int node, int start, int end, int l, int r) {
    if (r < start || end < l) return 0;           // out of range
    if (l <= start && end <= r) return tree[node]; // fully in range
    int mid = (start + end) / 2;
    return query(2*node, start, mid, l, r) + query(2*node+1, mid+1, end, l, r);
}

void update(int node, int start, int end, int idx, int val) {
    if (start == end) { tree[node] = val; return; }
    int mid = (start + end) / 2;
    if (idx <= mid) update(2*node, start, mid, idx, val);
    else update(2*node+1, mid+1, end, idx, val);
    tree[node] = tree[2*node] + tree[2*node+1];
}
```

## BIT (Fenwick Tree) Template
```java
int[] bit;
int n;

void update(int i, int delta) {
    for (; i <= n; i += i & (-i))  // add lowest set bit
        bit[i] += delta;
}

int query(int i) {                  // prefix sum [1..i]
    int sum = 0;
    for (; i > 0; i -= i & (-i))   // remove lowest set bit
        sum += bit[i];
    return sum;
}

int rangeQuery(int l, int r) {
    return query(r) - query(l - 1);
}
```

### Visualization: BIT Structure
```
Index:    1    2    3    4    5    6    7    8
bit[i]:  a[1] a[1..2] a[3] a[1..4] a[5] a[5..6] a[7] a[1..8]

Binary:   001  010    011  100    101  110    111  1000
Covers:   1    1-2    1    1-4    1    5-6    1    1-8

i & (-i) = lowest set bit = range each cell covers
```

---

# BIT MANIPULATION

## Essential Operations
```
x & (x-1)    → clear lowest set bit    [count bits, power of 2 check]
x & (-x)     → isolate lowest set bit  [BIT/Fenwick, iterate subsets]
x ^ x = 0    → self-cancel             [find unique element]
x | (1<<i)   → set bit i
x & (1<<i)   → check bit i
x ^ (1<<i)   → toggle bit i
x & mask     → extract bits
```

## Pattern: Single Number (XOR)
```java
// All appear twice except one
int result = 0;
for (int num : nums) result ^= num;
return result;

// Two unique numbers
int xor = 0;
for (int num : nums) xor ^= num;         // xor = a ^ b
int diff = xor & (-xor);                  // rightmost different bit
int a = 0, b = 0;
for (int num : nums) {
    if ((num & diff) == 0) a ^= num;      // group 1
    else b ^= num;                         // group 2
}
```

## Pattern: Counting Bits
```java
// Kernighan's: count set bits in x
int count = 0;
while (x != 0) { x &= (x-1); count++; }

// DP: countBits for 0..n
int[] dp = new int[n+1];
for (int i = 1; i <= n; i++)
    dp[i] = dp[i >> 1] + (i & 1);   // or dp[i & (i-1)] + 1
```

## Pattern: Subset Enumeration via Bitmask
```java
// Enumerate all subsets of a mask
for (int sub = mask; sub > 0; sub = (sub - 1) & mask) {
    // sub is a subset of mask
}

// Generate all 2^n subsets
for (int mask = 0; mask < (1 << n); mask++) {
    for (int i = 0; i < n; i++)
        if ((mask & (1 << i)) != 0)
            // element i is in this subset
}
```

---

# DESIGN PATTERNS

## Pattern: LRU Cache (HashMap + Doubly Linked List)
```java
class LRUCache {
    Map<Integer, DLLNode> map = new HashMap<>();
    DLLNode head, tail;  // sentinels
    int capacity;
    
    int get(int key) {
        if (!map.containsKey(key)) return -1;
        DLLNode node = map.get(key);
        moveToFront(node);
        return node.val;
    }
    
    void put(int key, int val) {
        if (map.containsKey(key)) {
            map.get(key).val = val;
            moveToFront(map.get(key));
        } else {
            if (map.size() == capacity) {
                map.remove(tail.prev.key);
                removeNode(tail.prev);  // evict LRU
            }
            DLLNode node = new DLLNode(key, val);
            map.put(key, node);
            addToFront(node);
        }
    }
}
```

## Pattern: LFU Cache
```
HashMap<key, Node>
HashMap<freq, DoublyLinkedList>   // per-frequency bucket (LRU within freq)
int minFreq

get/put: increase freq, move to new bucket
evict: remove tail of minFreq bucket (LRU among least frequent)
```

## Pattern: Rate Limiter
```
TOKEN BUCKET:         tokens refill at rate; burst up to capacity
SLIDING WINDOW LOG:   store timestamps, remove old, count < limit
SLIDING WINDOW COUNT: approximate using current + previous * overlap%
LEAKY BUCKET:         fixed output rate, queue overflow rejected
```

## Pattern: Consistent Hashing
```
Ring [0, 2^32): place V virtual nodes per server
Lookup: hash(key) → find next clockwise server node
Add server: only K/N keys migrate (minimal disruption)
```

---

# CONCURRENCY

## Pattern: Producer-Consumer
```java
class BoundedQueue<T> {
    final Queue<T> queue = new LinkedList<>();
    final int capacity;
    final Lock lock = new ReentrantLock();
    final Condition notFull = lock.newCondition();
    final Condition notEmpty = lock.newCondition();
    
    void put(T item) throws InterruptedException {
        lock.lock();
        try {
            while (queue.size() == capacity) notFull.await();
            queue.add(item);
            notEmpty.signal();
        } finally { lock.unlock(); }
    }
    
    T take() throws InterruptedException {
        lock.lock();
        try {
            while (queue.isEmpty()) notEmpty.await();
            T item = queue.poll();
            notFull.signal();
            return item;
        } finally { lock.unlock(); }
    }
}
```

## Pattern: Thread-Safe Singleton
```java
class Singleton {
    private static volatile Singleton instance;
    static Singleton getInstance() {
        if (instance == null) {
            synchronized (Singleton.class) {
                if (instance == null) instance = new Singleton();
            }
        }
        return instance;
    }
}
```

## Pattern: Sequencing (Print in Order)
```java
CountDownLatch latch1 = new CountDownLatch(1);
CountDownLatch latch2 = new CountDownLatch(1);

void first()  { print("first"); latch1.countDown(); }
void second() { latch1.await(); print("second"); latch2.countDown(); }
void third()  { latch2.await(); print("third"); }
```

## Pattern: Dining Philosophers
```
Solution 1: Resource ordering (always pick lower-numbered fork first)
Solution 2: Limit to N-1 philosophers trying simultaneously
Solution 3: Arbitrator mutex
```

---

# PREFIX SUM

## 1D Prefix Sum
```java
int[] prefix = new int[n + 1];
for (int i = 0; i < n; i++) prefix[i+1] = prefix[i] + nums[i];
// sum(l..r) = prefix[r+1] - prefix[l]
```

## 2D Prefix Sum
```java
int[][] pre = new int[m+1][n+1];
for (int i = 1; i <= m; i++)
    for (int j = 1; j <= n; j++)
        pre[i][j] = matrix[i-1][j-1] + pre[i-1][j] + pre[i][j-1] - pre[i-1][j-1];

// sum(r1,c1 to r2,c2):
int sum = pre[r2+1][c2+1] - pre[r1][c2+1] - pre[r2+1][c1] + pre[r1][c1];
```

## Difference Array (Range Updates)
```java
// Add val to range [l, r]:
diff[l] += val;
diff[r+1] -= val;

// Reconstruct: prefix sum of diff gives actual array
```

---

# SWEEP LINE

## Template
```java
List<int[]> events = new ArrayList<>();
for (int[] interval : intervals) {
    events.add(new int[]{interval[0], +1});   // start
    events.add(new int[]{interval[1], -1});   // end
}
events.sort((a,b) -> a[0] != b[0] ? a[0]-b[0] : a[1]-b[1]);

int active = 0, maxActive = 0;
for (int[] event : events) {
    active += event[1];
    maxActive = Math.max(maxActive, active);
}
```

## Applications
| Problem | Events | Track |
|---------|--------|-------|
| Max overlapping intervals | start(+1), end(-1) | max active |
| Meeting Rooms II | start(+1), end(-1) | max active = rooms needed |
| Skyline Problem | building start/end + height | active heights (TreeMap) |
| Rectangle Area | vertical sweeps + horizontal segments | active segments |

---

# DIVIDE AND CONQUER

## Merge Sort Based (Count Inversions)
```java
int mergeSort(int[] arr, int lo, int hi) {
    if (lo >= hi) return 0;
    int mid = (lo + hi) / 2;
    int count = mergeSort(arr, lo, mid) + mergeSort(arr, mid+1, hi);
    count += merge(arr, lo, mid, hi);  // count cross-inversions during merge
    return count;
}
```

## Quick Select (Kth Largest)
```java
int quickSelect(int[] nums, int lo, int hi, int k) {
    int pivot = partition(nums, lo, hi);
    if (pivot == k) return nums[k];
    else if (pivot < k) return quickSelect(nums, pivot+1, hi, k);
    else return quickSelect(nums, lo, pivot-1, k);
}
// Average O(n), worst O(n²) — randomize pivot for safety
```

---

# GAME THEORY

## Minimax Template
```java
int minimax(int[] state, boolean isMax, Map<Key, Integer> memo) {
    if (terminal(state)) return evaluate(state);
    if (memo.containsKey(key)) return memo.get(key);
    
    int best = isMax ? Integer.MIN_VALUE : Integer.MAX_VALUE;
    for (int move : moves(state)) {
        int val = minimax(apply(state, move), !isMax, memo);
        best = isMax ? Math.max(best, val) : Math.min(best, val);
    }
    memo.put(key, best);
    return best;
}
```

## Stone Game DP
```java
// dp[i][j] = max score difference for current player on piles[i..j]
for (int len = 2; len <= n; len++)
    for (int i = 0; i <= n - len; i++) {
        int j = i + len - 1;
        dp[i][j] = Math.max(piles[i] - dp[i+1][j], piles[j] - dp[i][j-1]);
    }
// First player wins if dp[0][n-1] > 0
```

## Nim Game
```
XOR all pile sizes. If XOR = 0 → second player wins. Else first player wins.
Sprague-Grundy: g(state) = mex({g(state') for each reachable state'})
```

---

# RECURSION PATTERNS

## Pattern: Divide and Return
```java
Result solve(input) {
    if (baseCase) return trivial;
    left = solve(leftHalf);
    right = solve(rightHalf);
    return merge(left, right);
}
```

## Pattern: Explore with State
```java
void explore(state) {
    if (goal) { collect(state); return; }
    for (choice in options) {
        if (valid(choice, state)) {
            applyChoice(state, choice);
            explore(state);
            undoChoice(state, choice);  // backtrack
        }
    }
}
```

## Pattern: Tree Recursion (Return Info Up)
```java
Info dfs(node) {
    if (leaf) return baseInfo;
    Info left = dfs(node.left);
    Info right = dfs(node.right);
    updateGlobal(left, right, node);    // uses both branches
    return computeReturn(left, right);  // single path up
}
```

## Recursion → Iteration Conversion
```
Tail recursion → while loop + accumulator
Tree recursion → explicit stack (DFS iterative)
Linear recursion → DP with memo or bottom-up table
```

---

# STRING MATCHING (KMP, Rabin-Karp, Z-Algorithm)

## KMP - O(n+m)
```java
// Build LPS array
int[] lps = new int[m];
for (int i = 1, len = 0; i < m; ) {
    if (pattern.charAt(i) == pattern.charAt(len)) lps[i++] = ++len;
    else if (len > 0) len = lps[len-1];
    else lps[i++] = 0;
}
// Search
for (int i = 0, j = 0; i < n; ) {
    if (text.charAt(i) == pattern.charAt(j)) { i++; j++; }
    if (j == m) { found(i-j); j = lps[j-1]; }
    else if (i < n && text.charAt(i) != pattern.charAt(j)) {
        if (j > 0) j = lps[j-1]; else i++;
    }
}
```

## Z-Algorithm
```
Z[i] = length of longest substring starting at i matching prefix
Concatenate: pattern + "$" + text
Z[i] >= len(pattern) → match at position i - m - 1
```

## Rabin-Karp (Rolling Hash)
```java
long hash = 0, patHash = 0, power = 1;
for (int i = 0; i < m; i++) {
    hash = (hash * BASE + text.charAt(i)) % MOD;
    patHash = (patHash * BASE + pattern.charAt(i)) % MOD;
    if (i > 0) power = power * BASE % MOD;
}
for (int i = m; i <= n; i++) {
    if (hash == patHash && verify(i-m)) found();
    if (i < n) {
        hash = ((hash - text.charAt(i-m) * power % MOD + MOD) * BASE + text.charAt(i)) % MOD;
    }
}
```
