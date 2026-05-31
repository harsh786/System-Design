# 11 - Monotonic Queue (Deque) Patterns

## Core Insight

A **monotonic deque** maintains elements in strictly increasing or decreasing order, enabling O(1) access to the min/max of a sliding window. Each element enters and exits the deque at most once, yielding **amortized O(n)** total work.

### Why O(n) Instead of O(nk)

| Approach | Per-window cost | Total | Notes |
|----------|----------------|-------|-------|
| Naive scan | O(k) | O(nk) | Re-examine all k elements each slide |
| Heap (lazy delete) | O(log k) | O(n log k) | Stale entries remain until popped |
| Segment Tree | O(log n) | O(n log n) | Heavy setup, overkill for sliding window |
| **Monotonic Deque** | **O(1) amortized** | **O(n)** | Each element pushed/popped once total |

**Key invariant:** The deque front always holds the answer (max or min) for the current window. Elements that can never be the answer are eagerly removed from the back before insertion.

---

## When to Use What

```
Need sliding window max/min?
├── Window size fixed, no updates? ──────────► Monotonic Deque O(n)
├── Window size dynamic, range queries? ─────► Segment Tree O(n log n)  
├── Need kth element in window? ─────────────► Ordered Set / Policy Tree
└── Need max/min but can tolerate O(n log n)?─► Heap with lazy deletion

Need to optimize DP[i] = max/min(DP[j]) + f(i) for j in some window?
└── Monotonic Deque (deque-optimized DP)
```

**Decision Flowchart:**
```
1. Is the problem about a contiguous subarray/window?
   YES → 2. Do you need max or min over that window?
          YES → 3. Is the window sliding (fixed or bounded size)?
                 YES → MONOTONIC DEQUE
                 NO  → Sparse Table / Segment Tree
          NO  → Other technique (prefix sums, two pointers, etc.)
   NO → 4. Is it a DP where transition looks at a bounded range of previous states?
         YES → DEQUE-OPTIMIZED DP
         NO  → Other technique
```

---

## Pattern 1: Sliding Window Maximum (LC 239)

### Signal
- Fixed-size window sliding across array
- Need maximum of each window position

### Invariant
Deque stores **indices** in **decreasing order of values**. Front = index of current window max.

### Template (Java)

```java
public int[] maxSlidingWindow(int[] nums, int k) {
    int n = nums.length;
    int[] result = new int[n - k + 1];
    Deque<Integer> dq = new ArrayDeque<>(); // stores indices

    for (int i = 0; i < n; i++) {
        // 1. Remove elements outside window from front
        while (!dq.isEmpty() && dq.peekFirst() < i - k + 1) {
            dq.pollFirst();
        }
        // 2. Remove smaller elements from back (they'll never be max)
        while (!dq.isEmpty() && nums[dq.peekLast()] <= nums[i]) {
            dq.pollLast();
        }
        // 3. Add current index
        dq.offerLast(i);
        // 4. Record answer once window is full
        if (i >= k - 1) {
            result[i - k + 1] = nums[dq.peekFirst()];
        }
    }
    return result;
}
```

### Step-by-Step Visualization

```
Input: nums = [1, 3, -1, -3, 5, 3, 6, 7], k = 3

i=0: num=1
     Deque (indices): [0]        values: [1]
     Window not full yet.

i=1: num=3
     Back removal: nums[0]=1 <= 3 → remove 0
     Deque: [1]                  values: [3]
     Window not full yet.

i=2: num=-1
     Back removal: nums[1]=3 > -1 → stop
     Deque: [1, 2]              values: [3, -1]
     Window [0..2] full. Answer = nums[1] = 3
     Result: [3]

i=3: num=-3
     Front removal: index 1 >= 3-3+1=1 → keep
     Back removal: nums[2]=-1 > -3 → stop
     Deque: [1, 2, 3]           values: [3, -1, -3]
     Front check: index 1 >= 3-3+1=1 ✓ (still in window)
     Answer = nums[1] = 3
     Result: [3, 3]

i=4: num=5
     Front removal: index 1 < 4-3+1=2 → remove 1
     Back removal: nums[3]=-3 <= 5 → remove 3
                   nums[2]=-1 <= 5 → remove 2
     Deque: [4]                  values: [5]
     Answer = nums[4] = 5
     Result: [3, 3, 5]

i=5: num=3
     Front removal: index 4 >= 5-3+1=3 ✓
     Back removal: nums[4]=5 > 3 → stop
     Deque: [4, 5]              values: [5, 3]
     Answer = nums[4] = 5
     Result: [3, 3, 5, 5]

i=6: num=6
     Front removal: index 4 >= 6-3+1=4 ✓
     Back removal: nums[5]=3 <= 6 → remove 5
                   nums[4]=5 <= 6 → remove 4
     Deque: [6]                  values: [6]
     Answer = nums[6] = 6
     Result: [3, 3, 5, 5, 6]

i=7: num=7
     Front removal: index 6 >= 7-3+1=5 ✓
     Back removal: nums[6]=6 <= 7 → remove 6
     Deque: [7]                  values: [7]
     Answer = nums[7] = 7
     Result: [3, 3, 5, 5, 6, 7]

Final: [3, 3, 5, 5, 6, 7]
```

### Complexity
- Time: O(n) — each element pushed and popped at most once
- Space: O(k) — deque holds at most k elements

---

## Pattern 2: Sliding Window Minimum

### Signal
- Same as above but need minimum
- Flip the deque to **increasing order**

### Template (Java)

```java
public int[] minSlidingWindow(int[] nums, int k) {
    int n = nums.length;
    int[] result = new int[n - k + 1];
    Deque<Integer> dq = new ArrayDeque<>();

    for (int i = 0; i < n; i++) {
        while (!dq.isEmpty() && dq.peekFirst() < i - k + 1) {
            dq.pollFirst();
        }
        // Remove LARGER elements from back (increasing deque)
        while (!dq.isEmpty() && nums[dq.peekLast()] >= nums[i]) {
            dq.pollLast();
        }
        dq.offerLast(i);
        if (i >= k - 1) {
            result[i - k + 1] = nums[dq.peekFirst()];
        }
    }
    return result;
}
```

### Invariant
Deque stores indices in **increasing order of values**. Front = index of current window min.

### Complexity
- Time: O(n), Space: O(k)

---

## Pattern 3: Shortest Subarray with Sum >= K (LC 862)

### Signal
- Subarray sum >= K, find **shortest** length
- Array may contain **negative numbers** (ruling out simple two-pointer)
- Prefix sums + monotonic deque

### Key Insight
Let `prefix[i] = nums[0] + ... + nums[i-1]`. Subarray sum `[j..i-1] = prefix[i] - prefix[j]`.
We want: find smallest `(i - j)` such that `prefix[i] - prefix[j] >= K`.

Two observations:
1. For a fixed `i`, we want the **largest** `j < i` where `prefix[j] <= prefix[i] - K`. But we want the **rightmost** such j (closest to i). So we scan from the front of an increasing deque.
2. If `prefix[j1] >= prefix[j2]` where `j1 < j2`, then `j1` is useless — `j2` gives both a larger subtraction result AND a shorter subarray. So maintain **increasing** prefix values in deque.

### Template (Java)

```java
public int shortestSubarray(int[] nums, int K) {
    int n = nums.length;
    long[] prefix = new long[n + 1];
    for (int i = 0; i < n; i++) {
        prefix[i + 1] = prefix[i] + nums[i];
    }

    int ans = Integer.MAX_VALUE;
    Deque<Integer> dq = new ArrayDeque<>(); // indices into prefix[]

    for (int i = 0; i <= n; i++) {
        // Pop from front: prefix[i] - prefix[front] >= K → valid answer
        while (!dq.isEmpty() && prefix[i] - prefix[dq.peekFirst()] >= K) {
            ans = Math.min(ans, i - dq.pollFirst());
        }
        // Pop from back: maintain increasing prefix values
        while (!dq.isEmpty() && prefix[dq.peekLast()] >= prefix[i]) {
            dq.pollLast();
        }
        dq.offerLast(i);
    }
    return ans == Integer.MAX_VALUE ? -1 : ans;
}
```

### Visualization

```
nums = [2, -1, 2], K = 3
prefix = [0, 2, 1, 3]

i=0: prefix[0]=0, dq=[] → add 0. Deque: [0]
i=1: prefix[1]=2, check front: 2-0=2 < 3. 
     Back: prefix[0]=0 < 2 → keep. Deque: [0, 1]
i=2: prefix[2]=1, check front: 1-0=1 < 3.
     Back: prefix[1]=2 >= 1 → remove 1. prefix[0]=0 < 1 → keep.
     Deque: [0, 2]
i=3: prefix[3]=3, check front: 3-0=3 >= 3 → ans=3-0=3, pop 0.
     Check front: 3-1=2 < 3 → stop.
     Back: prefix[2]=1 < 3 → keep. Deque: [2, 3]

Answer: 3 (entire array [2,-1,2])
```

### Why This Handles Negatives
Two-pointer fails with negatives because shrinking the window can increase the sum. The prefix-sum + monotonic deque approach doesn't assume monotonicity of prefix — it explicitly maintains only useful candidates.

### Complexity
- Time: O(n), Space: O(n)

---

## Pattern 4: Longest Subarray with Limit (LC 1438)

### Signal
- Longest subarray where `max - min <= limit`
- Two deques: one for max (decreasing), one for min (increasing)
- Sliding window with variable size

### Template (Java)

```java
public int longestSubarray(int[] nums, int limit) {
    Deque<Integer> maxDq = new ArrayDeque<>(); // decreasing
    Deque<Integer> minDq = new ArrayDeque<>(); // increasing
    int left = 0, ans = 0;

    for (int right = 0; right < nums.length; right++) {
        // Maintain decreasing deque for max
        while (!maxDq.isEmpty() && nums[maxDq.peekLast()] <= nums[right]) {
            maxDq.pollLast();
        }
        maxDq.offerLast(right);

        // Maintain increasing deque for min
        while (!minDq.isEmpty() && nums[minDq.peekLast()] >= nums[right]) {
            minDq.pollLast();
        }
        minDq.offerLast(right);

        // Shrink window if constraint violated
        while (nums[maxDq.peekFirst()] - nums[minDq.peekFirst()] > limit) {
            left++;
            if (maxDq.peekFirst() < left) maxDq.pollFirst();
            if (minDq.peekFirst() < left) minDq.pollFirst();
        }

        ans = Math.max(ans, right - left + 1);
    }
    return ans;
}
```

### Invariant
- `maxDq` front = index of max in `[left, right]`
- `minDq` front = index of min in `[left, right]`
- Window is valid iff `max - min <= limit`

### Complexity
- Time: O(n), Space: O(n)

---

## Pattern 5: Jump Game VI (LC 1696)

### Signal
- DP where `dp[i] = nums[i] + max(dp[i-k]...dp[i-1])`
- Optimize the max lookup over a sliding window of size k

### Template (Java)

```java
public int maxResult(int[] nums, int k) {
    int n = nums.length;
    int[] dp = new int[n];
    dp[0] = nums[0];
    Deque<Integer> dq = new ArrayDeque<>(); // decreasing deque of dp values (stores indices)
    dq.offerLast(0);

    for (int i = 1; i < n; i++) {
        // Remove out-of-window indices
        while (!dq.isEmpty() && dq.peekFirst() < i - k) {
            dq.pollFirst();
        }
        // Transition: best reachable state + current value
        dp[i] = dp[dq.peekFirst()] + nums[i];
        // Maintain decreasing order of dp values
        while (!dq.isEmpty() && dp[dq.peekLast()] <= dp[i]) {
            dq.pollLast();
        }
        dq.offerLast(i);
    }
    return dp[n - 1];
}
```

### Visualization

```
nums = [1, -1, -2, 4, -7, 3], k = 2

i=0: dp[0]=1, dq=[0]
i=1: window=[0], max dp = dp[0]=1. dp[1]=1+(-1)=0
     Back: dp[0]=1 > 0 → keep. dq=[0,1]
i=2: window=[0,1]→both valid. max dp = dp[0]=1. dp[2]=1+(-2)=-1
     Back: dp[1]=0 > -1 → keep. dq=[0,1,2]
i=3: Front: 0 < 3-2=1 → remove. dq=[1,2]
     max dp = dp[1]=0. dp[3]=0+4=4
     Back: dp[2]=-1 <= 4 → remove. dp[1]=0 <= 4 → remove. dq=[3]
i=4: window=[3]. dp[4]=dp[3]+(-7)=4-7=-3
     Back: dp[3]=4 > -3 → keep. dq=[3,4]
i=5: Front: 3 < 5-2=3? No (3>=3). max dp = dp[3]=4. dp[5]=4+3=7
     Back: dp[4]=-3 <= 7 → remove. dp[3]=4 <= 7 → remove. dq=[5]

Answer: dp[5] = 7
Path: 0→3→5 (values 1+4+3=8? Let me recheck)
Actually dp[5] = dp[3]+3 = 4+3 = 7. dp[3] = dp[1]+4 = 0+4 = 4. dp[1] = dp[0]-1 = 0.
Total score accumulated = 7. ✓
```

### Complexity
- Time: O(n), Space: O(n)

---

## Pattern 6: Constrained Subsequence Sum (LC 1425)

### Signal
- Maximum sum subsequence where adjacent selected elements are at most k apart
- `dp[i] = nums[i] + max(0, max(dp[i-k]...dp[i-1]))`
- Nearly identical to Jump Game VI but with optional "restart"

### Template (Java)

```java
public int constrainedSubsetSum(int[] nums, int k) {
    int n = nums.length;
    int[] dp = new int[n];
    Deque<Integer> dq = new ArrayDeque<>();
    int ans = Integer.MIN_VALUE;

    for (int i = 0; i < n; i++) {
        // Remove out-of-window
        while (!dq.isEmpty() && dq.peekFirst() < i - k) {
            dq.pollFirst();
        }
        // dp[i] = nums[i] + max(0, best previous in window)
        dp[i] = nums[i] + (dq.isEmpty() ? 0 : Math.max(0, dp[dq.peekFirst()]));

        // Maintain decreasing deque
        while (!dq.isEmpty() && dp[dq.peekLast()] <= dp[i]) {
            dq.pollLast();
        }
        dq.offerLast(i);

        ans = Math.max(ans, dp[i]);
    }
    return ans;
}
```

### Key Difference from Jump Game VI
- Not forced to include every element — can "restart" by taking `max(0, prevBest)`
- Must track global max answer (not just `dp[n-1]`)

### Complexity
- Time: O(n), Space: O(n)

---

## Pattern 7: Max Value of Equation (LC 1499)

### Signal
- Given points sorted by x: maximize `yi + yj + |xi - xj|` where `xi < xj` and `xj - xi <= k`
- Since sorted: `|xi - xj| = xj - xi`
- Rewrite: `(yj + xj) + (yi - xi)` — maximize `(yi - xi)` for valid i's

### Template (Java)

```java
public int findMaxValueOfEquation(int[][] points, int k) {
    // Maximize (yj + xj) + (yi - xi) where xj - xi <= k, i < j
    Deque<int[]> dq = new ArrayDeque<>(); // [xi, yi - xi], decreasing by (y-x)
    int ans = Integer.MIN_VALUE;

    for (int[] p : points) {
        int xj = p[0], yj = p[1];

        // Remove points too far away (xj - xi > k)
        while (!dq.isEmpty() && xj - dq.peekFirst()[0] > k) {
            dq.pollFirst();
        }

        // Update answer with front (max yi - xi in valid range)
        if (!dq.isEmpty()) {
            ans = Math.max(ans, yj + xj + dq.peekFirst()[1]);
        }

        // Maintain decreasing order of (y - x) from front to back
        int val = yj - xj;
        while (!dq.isEmpty() && dq.peekLast()[1] <= val) {
            dq.pollLast();
        }
        dq.offerLast(new int[]{xj, val});
    }
    return ans;
}
```

### Decomposition Trick
The core technique: **split the objective into a part depending only on j and a part depending only on i**, then use the deque to optimize the "best i" lookup.

```
yi + yj + |xi - xj|   (xi < xj, sorted)
= (yj + xj) + (yi - xi)
     ↑ fixed for j    ↑ maximize over valid i's using deque
```

### Complexity
- Time: O(n), Space: O(n)

---

## Summary: The Monotonic Deque Meta-Pattern

```java
// Generic template for deque-optimized sliding window / DP
Deque<Integer> dq = new ArrayDeque<>();

for (int i = 0; i < n; i++) {
    // STEP 1: Evict expired elements from front
    while (!dq.isEmpty() && expired(dq.peekFirst(), i)) {
        dq.pollFirst();
    }

    // STEP 2: Query — front of deque is the optimal value
    answer = query(dq.peekFirst());

    // STEP 3: Maintain monotonicity — remove dominated elements from back
    while (!dq.isEmpty() && dominated(dq.peekLast(), i)) {
        dq.pollLast();
    }

    // STEP 4: Insert current element
    dq.offerLast(i);
}
```

| Step | Purpose | Decreasing Deque (max) | Increasing Deque (min) |
|------|---------|----------------------|----------------------|
| Evict | Window bounds | `front < i - k + 1` | Same |
| Query | Get answer | `nums[front]` = max | `nums[front]` = min |
| Maintain | Remove losers | Remove `back <= current` | Remove `back >= current` |

---

## Variant Comparison Table

| Problem | Deque Type | What's Stored | Window Constraint | DP? |
|---------|-----------|---------------|-------------------|-----|
| Sliding Window Max | Decreasing | Indices | Fixed size k | No |
| Sliding Window Min | Increasing | Indices | Fixed size k | No |
| Shortest Subarray Sum>=K | Increasing (prefix) | Prefix indices | Variable (pop front greedily) | No |
| Longest with Limit | Both | Indices | Variable (shrink left) | No |
| Jump Game VI | Decreasing (dp) | Indices | Last k states | Yes |
| Constrained Subseq Sum | Decreasing (dp) | Indices | Last k states | Yes |
| Max Equation Value | Decreasing (y-x) | [x, y-x] pairs | xj - xi <= k | No |

---

## Common Mistakes

1. **Storing values instead of indices** — You need indices to check window expiry.
2. **Wrong comparison direction** — `<=` vs `<` matters. Use `<=` to remove equal elements (keeps rightmost, often correct for "latest" semantics).
3. **Forgetting the front eviction step** — Without it, stale elements corrupt answers.
4. **Using `>=` in back removal for max-deque** — Should be `<=`. (Deque is decreasing, remove smaller-or-equal from back.)
5. **Not handling the "query before insert" vs "insert before query" ordering** — For equation-style problems, query first (current j looks at previous i's), then insert current as future candidate.
