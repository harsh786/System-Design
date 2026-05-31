# Dynamic Programming - Pattern Guide

> DP = Optimal Substructure + Overlapping Subproblems. If you can write a recurrence, you can write DP.

---

## DP Pattern Taxonomy (Decision Tree)

```
What type of DP?
│
├─ Single array/sequence?
│   ├─ Answer depends on prev 1-2 states? ──→ LINEAR DP (Fibonacci/House Robber)
│   ├─ Longest subsequence with property? ──→ LIS PATTERN
│   └─ Stock buy/sell with rules? ──────────→ STATE MACHINE DP
│
├─ Select items with capacity constraint?
│   ├─ Each item used once? ────────────────→ 0/1 KNAPSACK
│   ├─ Unlimited use? ─────────────────────→ UNBOUNDED KNAPSACK
│   └─ Partition into groups? ──────────────→ SUBSET SUM / PARTITION
│
├─ Two strings/sequences? ─────────────────→ TWO-STRING DP (LCS/Edit Distance)
│
├─ 2D grid traversal? ────────────────────→ GRID DP
│
├─ Optimal way to split range [i..j]? ────→ INTERVAL DP
│
├─ Tree structure? ────────────────────────→ TREE DP
│
└─ Small set (n ≤ 20), track used? ───────→ BITMASK DP
```

---

## The 5-Step DP Framework

```
For ANY DP problem:
1. DEFINE STATE:      What variables uniquely describe a subproblem?
2. RECURRENCE:        How do I compute state from smaller states?
3. BASE CASE:         What are the trivial subproblems?
4. COMPUTATION ORDER: Bottom-up (which cells must be filled first)?
5. ANSWER LOCATION:   Where in the table is the final answer?
6. (BONUS) OPTIMIZE:  Can I reduce space? (rolling array, 1D instead of 2D)
```

---

## Pattern 1: Linear DP - Fibonacci Style

**Signal:** Answer at step n depends on previous 1-2 steps. Combinatorial counting.

### Template
```java
// dp[i] = number of ways / optimal value at position i
dp[0] = base0;
dp[1] = base1;
for (int i = 2; i <= n; i++) {
    dp[i] = dp[i-1] + dp[i-2];  // or other combination
}

// Space optimization:
int prev2 = base0, prev1 = base1;
for (int i = 2; i <= n; i++) {
    int curr = prev1 + prev2;
    prev2 = prev1;
    prev1 = curr;
}
```

### Problems in this Pattern
| Problem | Recurrence |
|---------|-----------|
| Climbing Stairs | dp[i] = dp[i-1] + dp[i-2] |
| Decode Ways | dp[i] = dp[i-1] (if valid 1-digit) + dp[i-2] (if valid 2-digit) |
| Tribonacci | dp[i] = dp[i-1] + dp[i-2] + dp[i-3] |
| Domino Tiling | dp[i] = dp[i-1] + dp[i-2] (for 2xN) |

---

## Pattern 2: Linear DP - Skip/Take (House Robber)

**Signal:** Choose elements from sequence with constraints (can't take adjacent).

### Template
```java
// dp[i] = max value considering elements 0..i
dp[0] = nums[0];
dp[1] = Math.max(nums[0], nums[1]);
for (int i = 2; i < n; i++) {
    dp[i] = Math.max(
        dp[i-1],              // SKIP current
        dp[i-2] + nums[i]    // TAKE current (must skip previous)
    );
}

// Space optimized:
int skip = 0, take = nums[0];
for (int i = 1; i < n; i++) {
    int newTake = skip + nums[i];
    skip = Math.max(skip, take);
    take = newTake;
}
```

### Variants
| Variant | Modification |
|---------|-------------|
| House Robber II (circular) | max(rob[0..n-2], rob[1..n-1]) — exclude either end |
| House Robber III (tree) | dfs returns (rob_this, skip_this) pair |
| Delete and Earn | Transform: count frequencies, then House Robber on values |

---

## Pattern 3: Longest Increasing Subsequence (LIS)

**Signal:** Longest subsequence with ordering/monotonicity constraint.

### O(n²) DP
```java
int[] dp = new int[n];  // dp[i] = LIS ending at index i
Arrays.fill(dp, 1);
for (int i = 1; i < n; i++)
    for (int j = 0; j < i; j++)
        if (nums[j] < nums[i])
            dp[i] = Math.max(dp[i], dp[j] + 1);
return Arrays.stream(dp).max().getAsInt();
```

### O(n log n) Patience Sorting
```java
List<Integer> tails = new ArrayList<>();  // tails[i] = smallest tail of LIS of length i+1
for (int num : nums) {
    int pos = Collections.binarySearch(tails, num);
    if (pos < 0) pos = -(pos + 1);
    if (pos == tails.size()) tails.add(num);
    else tails.set(pos, num);
}
return tails.size();
```

### Visualization
```
nums: [10, 9, 2, 5, 3, 7, 101, 18]

tails evolution:
  [10]          ← start
  [9]           ← 9 replaces 10 (smaller tail for length 1)
  [2]           ← 2 replaces 9
  [2, 5]       ← 5 extends (new length 2)
  [2, 3]       ← 3 replaces 5 (smaller tail for length 2)
  [2, 3, 7]    ← 7 extends
  [2, 3, 7, 101] ← 101 extends
  [2, 3, 7, 18]  ← 18 replaces 101

LIS length = 4 (e.g., [2, 3, 7, 101])

NOTE: tails array is NOT the actual LIS!
      It just tracks the potential for extension.
```

### Related Problems
- Longest Chain of Pairs
- Russian Doll Envelopes (2D LIS: sort by width, LIS on heights)
- Number of Longest Increasing Subsequences (track count[] alongside dp[])

---

## Pattern 4: 0/1 Knapsack

**Signal:** Select items (each used once) with weight constraint, maximize value.

### Template (2D)
```java
// dp[i][w] = max value using items 0..i-1 with capacity w
int[][] dp = new int[n+1][W+1];
for (int i = 1; i <= n; i++)
    for (int w = 0; w <= W; w++) {
        dp[i][w] = dp[i-1][w];  // don't take item i
        if (weight[i-1] <= w)
            dp[i][w] = Math.max(dp[i][w], dp[i-1][w - weight[i-1]] + value[i-1]);
    }
```

### Template (1D optimized - iterate capacity BACKWARDS)
```java
int[] dp = new int[W+1];
for (int i = 0; i < n; i++)
    for (int w = W; w >= weight[i]; w--)  // RIGHT TO LEFT (ensures each item used once)
        dp[w] = Math.max(dp[w], dp[w - weight[i]] + value[i]);
```

### Why Backwards?
```
If we go left to right: dp[w - weight[i]] might already include item i
  → item reused (unbounded knapsack behavior)
Going right to left: dp[w - weight[i]] is from previous item's row
  → each item used at most once ✓
```

### Problems Mapped to 0/1 Knapsack
| Problem | Items | Weight | Value | Capacity |
|---------|-------|--------|-------|----------|
| Partition Equal Subset Sum | nums | nums[i] | N/A | totalSum/2 |
| Target Sum (+/-) | nums | nums[i] | N/A | (sum+target)/2 |
| Last Stone Weight II | stones | stones[i] | N/A | totalSum/2 |
| Ones and Zeroes | strings | (zeros,ones) | 1 per string | (m zeros, n ones) |

---

## Pattern 5: Unbounded Knapsack

**Signal:** Items can be used unlimited times. Coin change, rod cutting.

### Template (iterate capacity LEFT TO RIGHT)
```java
int[] dp = new int[W+1];
for (int i = 0; i < n; i++)
    for (int w = weight[i]; w <= W; w++)  // LEFT TO RIGHT (reuse allowed)
        dp[w] = Math.max(dp[w], dp[w - weight[i]] + value[i]);
```

### Coin Change (Minimize)
```java
int[] dp = new int[amount + 1];
Arrays.fill(dp, Integer.MAX_VALUE);
dp[0] = 0;
for (int coin : coins)
    for (int a = coin; a <= amount; a++)
        if (dp[a - coin] != Integer.MAX_VALUE)
            dp[a] = Math.min(dp[a], dp[a - coin] + 1);
```

### Coin Change II (Count Ways)
```java
int[] dp = new int[amount + 1];
dp[0] = 1;
for (int coin : coins)           // outer loop: coins (avoids counting permutations)
    for (int a = coin; a <= amount; a++)
        dp[a] += dp[a - coin];
```

### Combination Sum IV (Order Matters = Permutations)
```java
int[] dp = new int[target + 1];
dp[0] = 1;
for (int a = 1; a <= target; a++)     // outer loop: amounts
    for (int num : nums)               // inner loop: choices
        if (a >= num) dp[a] += dp[a - num];
```

**Key Insight:**
- Coins outer, amount inner → **combinations** (order doesn't matter)
- Amount outer, coins inner → **permutations** (order matters)

---

## Pattern 6: Two-String DP

**Signal:** Compare/transform two sequences.

### LCS (Longest Common Subsequence)
```java
int[][] dp = new int[m+1][n+1];
for (int i = 1; i <= m; i++)
    for (int j = 1; j <= n; j++)
        if (s1.charAt(i-1) == s2.charAt(j-1))
            dp[i][j] = dp[i-1][j-1] + 1;
        else
            dp[i][j] = Math.max(dp[i-1][j], dp[i][j-1]);
```

### Edit Distance
```java
int[][] dp = new int[m+1][n+1];
for (int i = 0; i <= m; i++) dp[i][0] = i;
for (int j = 0; j <= n; j++) dp[0][j] = j;

for (int i = 1; i <= m; i++)
    for (int j = 1; j <= n; j++)
        if (s1.charAt(i-1) == s2.charAt(j-1))
            dp[i][j] = dp[i-1][j-1];
        else
            dp[i][j] = 1 + Math.min(dp[i-1][j-1],    // replace
                            Math.min(dp[i-1][j],       // delete from s1
                                     dp[i][j-1]));     // insert into s1
```

### Visualization: Edit Distance
```
     ""  r  o  s
""    0  1  2  3
h     1  1  2  3
o     2  2  1  2
r     3  2  2  2
s     4  3  3  2
e     5  4  4  3

"horse" → "ros" = 3 operations
Path: horse → rorse (replace h→r) → rose (delete r) → ros (delete e)
```

### Related Problems
| Problem | Recurrence |
|---------|-----------|
| Longest Common Subsequence | match → diag+1, else max(left, up) |
| Edit Distance | match → diag, else 1+min(diag, up, left) |
| Distinct Subsequences | match → diag + left (count matches), else left |
| Interleaving String | 3D or 2D: can form s3[i+j] from s1[i] or s2[j]? |
| Wildcard Matching | '*' → match 0 (left) or match 1+ (up) |
| Regular Expression | '.' → any, '*' → 0 match (dp[i][j-2]) or 1+ match |

---

## Pattern 7: Interval DP

**Signal:** Optimal way to split/merge range [i..j], consider all split points.

### Template
```java
// Fill by increasing length
for (int len = 2; len <= n; len++) {
    for (int i = 0; i <= n - len; i++) {
        int j = i + len - 1;
        dp[i][j] = initial;
        for (int k = i; k < j; k++) {  // try all split points
            dp[i][j] = Math.min(dp[i][j],
                dp[i][k] + dp[k+1][j] + cost(i, j, k));
        }
    }
}
```

### Burst Balloons (Classic Interval DP)
```java
// Key insight: think about which balloon to burst LAST in range (i,j)
// dp[i][j] = max coins from bursting all balloons between i and j (exclusive)
for (int len = 2; len <= n+1; len++)
    for (int i = 0; i <= n+1 - len; i++) {
        int j = i + len - 1;
        for (int k = i+1; k < j; k++)  // k = last to burst
            dp[i][j] = Math.max(dp[i][j],
                dp[i][k] + dp[k][j] + nums[i] * nums[k] * nums[j]);
    }
```

### Matrix Chain Multiplication
```
Multiply A1 × A2 × ... × An with minimum scalar multiplications
dp[i][j] = min cost to multiply matrices i..j
dp[i][j] = min over k: dp[i][k] + dp[k+1][j] + dims[i]*dims[k+1]*dims[j+1]
```

### Palindrome Partitioning II (Min Cuts)
```
dp[i] = min cuts for s[0..i]
dp[i] = min(dp[j-1] + 1) for all j where s[j..i] is palindrome
Precompute isPalin[i][j] with expand or DP
```

---

## Pattern 8: State Machine DP (Stock Trading)

**Signal:** Multiple states/phases, transitions between states with rules.

### General Stock Template
```java
// States: hold (bought, holding stock), cash (sold, no stock)
int hold = -prices[0], cash = 0;
for (int i = 1; i < n; i++) {
    int newHold = Math.max(hold, cash - prices[i]);     // buy or keep holding
    int newCash = Math.max(cash, hold + prices[i]);     // sell or stay in cash
    hold = newHold;
    cash = newCash;
}
return cash;
```

### State Machine Diagram
```
         buy (-price)
    ┌────────────────────────┐
    │                        │
    ▼         sell (+price)  │
 ┌──────┐  ────────────→  ┌──────┐
 │ HOLD │                  │ CASH │
 └──────┘  ←────────────  └──────┘
    │         buy (-price)    │
    │                         │
    └─── hold (do nothing) ───┘─── rest (do nothing)
```

### All Stock Variants

| Variant | Modification |
|---------|-------------|
| Buy/Sell I (1 transaction) | Track min price, max profit |
| Buy/Sell II (unlimited) | Simple state machine above |
| Buy/Sell III (2 transactions) | buy1, sell1, buy2, sell2 states |
| Buy/Sell IV (k transactions) | buy[k], sell[k] arrays |
| With Cooldown | Add REST state: cash→rest→can_buy |
| With Fee | Deduct fee on sell: cash = hold + price - fee |

### K Transactions
```java
int[] buy = new int[k+1], sell = new int[k+1];
Arrays.fill(buy, Integer.MIN_VALUE);
for (int price : prices) {
    for (int t = 1; t <= k; t++) {
        buy[t] = Math.max(buy[t], sell[t-1] - price);
        sell[t] = Math.max(sell[t], buy[t] + price);
    }
}
return sell[k];
```

---

## Pattern 9: Tree DP

**Signal:** Optimization on tree where answer at node depends on children's answers.

### Template
```java
int globalAnswer = 0;

int dfs(TreeNode node) {
    if (node == null) return 0;
    int left = dfs(node.left);
    int right = dfs(node.right);
    
    // Update global answer (uses BOTH branches through this node)
    globalAnswer = Math.max(globalAnswer, combine(left, right, node));
    
    // Return to parent (single branch extending upward)
    return singleBranch(left, right, node);
}
```

### Examples
```
MAX PATH SUM:
  left = max(0, dfs(left))      // ignore negative
  right = max(0, dfs(right))
  global = max(global, left + right + node.val)
  return max(left, right) + node.val

HOUSE ROBBER III:
  int[] dfs(node) → [robThis, skipThis]
  robThis = node.val + left[1] + right[1]  // rob this, skip children
  skipThis = max(left[0], left[1]) + max(right[0], right[1])
  
LONGEST PATH (same value):
  int left = dfs(left), right = dfs(right)
  l = (node.val == node.left.val) ? left + 1 : 0
  r = (node.val == node.right.val) ? right + 1 : 0
  global = max(global, l + r)
  return max(l, r)
```

---

## Pattern 10: Bitmask DP

**Signal:** Small set (n ≤ 20), need to track which elements are "used".

### Template
```java
// dp[mask] = optimal value when elements in mask are used
int[] dp = new int[1 << n];
Arrays.fill(dp, initial);
dp[0] = base;

for (int mask = 0; mask < (1 << n); mask++) {
    int k = Integer.bitCount(mask);  // how many bits set = how many assigned
    for (int i = 0; i < n; i++) {
        if ((mask & (1 << i)) != 0) continue;  // i already used
        int newMask = mask | (1 << i);
        dp[newMask] = optimize(dp[newMask], dp[mask] + cost(k, i));
    }
}
```

### TSP (Traveling Salesman)
```java
// dp[mask][i] = min cost to visit cities in mask, ending at city i
dp[1][0] = 0;  // start at city 0
for (int mask = 1; mask < (1 << n); mask++)
    for (int u = 0; u < n; u++) {
        if ((mask & (1 << u)) == 0) continue;
        for (int v = 0; v < n; v++) {
            if ((mask & (1 << v)) != 0) continue;
            int newMask = mask | (1 << v);
            dp[newMask][v] = Math.min(dp[newMask][v], dp[mask][u] + dist[u][v]);
        }
    }
// Answer: min(dp[(1<<n)-1][i] + dist[i][0]) for all i
```

### Common Bitmask Problems
- TSP (Shortest Hamiltonian Path)
- Assign n tasks to n workers (Hungarian alternative)
- Can I Win (game theory + memoization)
- Parallel Courses II (min semesters with k limit)
- Shortest Superstring

**Complexity:** O(2^n * n) time, O(2^n) space

---

## Pattern 11: Digit DP

**Signal:** Count numbers in range [L, R] with digit property (divisible, digit sum, no repeated digits).

### Template
```java
// dp(pos, tight, state) = count of valid numbers
// pos: current digit position
// tight: are we still bounded by the limit?
// state: problem-specific (sum, mask, last digit, etc.)

long solve(String num, int pos, boolean tight, int state, Long[][][] memo) {
    if (pos == num.length()) return isValid(state) ? 1 : 0;
    if (memo[pos][tight?1:0][state] != null) return memo[pos][tight?1:0][state];
    
    int limit = tight ? (num.charAt(pos) - '0') : 9;
    long count = 0;
    for (int d = 0; d <= limit; d++) {
        count += solve(num, pos + 1, tight && (d == limit), newState(state, d), memo);
    }
    return memo[pos][tight?1:0][state] = count;
}

// count(L, R) = solve(R) - solve(L-1)
```

---

## Master DP Decision Table

| Problem Characteristics | Pattern | Key Idea |
|---|---|---|
| f(n) depends on f(n-1), f(n-2) | Linear/Fibonacci | Rolling variables |
| Take or skip with constraints | House Robber | dp = max(skip, take+prev_valid) |
| Longest subsequence | LIS | dp[i] = max(dp[j]+1) or patience sort |
| Items + capacity, use once | 0/1 Knapsack | dp[w] backwards |
| Items + capacity, reuse OK | Unbounded Knapsack | dp[w] forwards |
| Two strings comparison | 2-String DP | dp[i][j] on prefixes |
| Grid paths/costs | Grid DP | dp[i][j] from top-left |
| Optimal split of range | Interval DP | dp[i][j] try all k |
| Multiple states/phases | State Machine | Separate dp per state |
| Tree optimization | Tree DP | dfs returns to parent |
| Track subset used (n≤20) | Bitmask DP | dp[mask] |
| Count numbers with property | Digit DP | dp(pos, tight, state) |
