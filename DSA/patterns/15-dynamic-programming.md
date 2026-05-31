# Dynamic Programming Patterns - Complete Guide

## The 5-Step DP Framework

```
Step 1: DEFINE STATE    → What does dp[i] (or dp[i][j]) represent?
Step 2: RECURRENCE      → How does dp[i] relate to smaller subproblems?
Step 3: BASE CASE       → What are the trivial answers?
Step 4: ORDER           → In what order do we fill the table?
Step 5: ANSWER          → Where in the table is the final answer?
```

## DP Pattern Taxonomy

```
                            Dynamic Programming
                                    │
        ┌───────────┬───────────┬───┴───┬──────────┬──────────────┐
        │           │           │       │          │              │
    Linear DP    Knapsack   String DP  Grid DP  Advanced       Special
        │           │           │       │          │              │
   ┌────┼────┐   ┌──┴──┐    ┌──┴──┐   │    ┌─────┼─────┐    ┌──┴──┐
   │    │    │   │     │    │     │   │    │     │     │    │     │
 Fib  Skip  LIS 0/1  Unb  LCS  Edit  │  Interval State  │  Bit  Digit
      Take            ound       Dist │    DP    Machine │  mask  DP
                                      │          DP      │
                                    Grid         │     Tree DP
                                    paths      Stock
                                              variants
```

## Master Decision Table

| Problem Characteristics | Pattern | Key Indicator |
|---|---|---|
| "How many ways to reach step n" | Linear DP (Fibonacci) | Sequential decisions, f(n) = f(n-1) + f(n-2) |
| "Max profit, can't pick adjacent" | Skip/Take (House Robber) | Adjacent constraint |
| "Longest increasing/decreasing" | LIS | Subsequence + monotonic condition |
| "Select items with weight limit" | 0/1 Knapsack | Each item used once, capacity constraint |
| "Unlimited supply, target sum" | Unbounded Knapsack | Items reusable, combinations/min count |
| "Transform string A → B" | Two-String DP | Two sequences, align/match/edit |
| "Navigate grid top-left → bottom-right" | Grid DP | 2D matrix traversal |
| "Merge/split cost optimization" | Interval DP | Optimal merge, O(n³) |
| "Multiple states with transitions" | State Machine DP | Cooldown, hold/sell/rest |
| "Optimal value in tree structure" | Tree DP | DFS, return (take, skip) pair |
| "Assign n items (n ≤ 20)" | Bitmask DP | Small n, all subsets |
| "Count numbers with property in [L,R]" | Digit DP | Digit-by-digit construction |

---

## 1. Linear DP - Fibonacci Style

### Signal
- "How many ways to reach state n?"
- Each state depends on a fixed number of previous states
- Problems: Climbing Stairs, Decode Ways, Tribonacci

### Key Recurrence
```
dp[i] = dp[i-1] + dp[i-2]           // Climbing Stairs
dp[i] = dp[i-1] + (valid2 ? dp[i-2] : 0)  // Decode Ways
```

### Template (Java)

```java
// Climbing Stairs
public int climbStairs(int n) {
    if (n <= 2) return n;
    int prev2 = 1, prev1 = 2;
    for (int i = 3; i <= n; i++) {
        int curr = prev1 + prev2;
        prev2 = prev1;
        prev1 = curr;
    }
    return prev1;
}

// Decode Ways - "226" → how many decodings?
public int numDecodings(String s) {
    int n = s.length();
    int prev2 = 1, prev1 = s.charAt(0) == '0' ? 0 : 1;
    for (int i = 2; i <= n; i++) {
        int curr = 0;
        int oneDigit = s.charAt(i - 1) - '0';
        int twoDigit = Integer.parseInt(s.substring(i - 2, i));
        if (oneDigit >= 1) curr += prev1;
        if (twoDigit >= 10 && twoDigit <= 26) curr += prev2;
        prev2 = prev1;
        prev1 = curr;
    }
    return prev1;
}
```

### Visualization
```
Climbing Stairs (n=5):
dp: [1, 1, 2, 3, 5, 8]
     0  1  2  3  4  5
                      ↑ answer

Decode Ways "226":
Index:    0   1   2   3
Char:         2   2   6
dp:      [1] [1] [2] [3]
              ↑    ↑    ↑
             "2"  "22"  "226" → 3 ways: 2-2-6, 22-6, 2-26
```

### Complexity
- Time: O(n), Space: O(1) with rolling variables

---

## 2. Linear DP - Skip/Take (House Robber)

### Signal
- "Cannot pick two adjacent elements"
- "Maximum sum/profit with adjacency constraint"
- Problems: House Robber I/II, Delete and Earn

### Key Recurrence
```
dp[i] = max(dp[i-1], dp[i-2] + nums[i])
         ↑ skip i     ↑ take i
```

### Template (Java)

```java
// House Robber I
public int rob(int[] nums) {
    int prev2 = 0, prev1 = 0;
    for (int num : nums) {
        int curr = Math.max(prev1, prev2 + num);
        prev2 = prev1;
        prev1 = curr;
    }
    return prev1;
}

// House Robber II (circular - first and last are adjacent)
public int robCircular(int[] nums) {
    if (nums.length == 1) return nums[0];
    // Rob houses [0..n-2] OR [1..n-1], take max
    return Math.max(
        robRange(nums, 0, nums.length - 2),
        robRange(nums, 1, nums.length - 1)
    );
}

private int robRange(int[] nums, int lo, int hi) {
    int prev2 = 0, prev1 = 0;
    for (int i = lo; i <= hi; i++) {
        int curr = Math.max(prev1, prev2 + nums[i]);
        prev2 = prev1;
        prev1 = curr;
    }
    return prev1;
}

// Delete and Earn - reduce to House Robber
public int deleteAndEarn(int[] nums) {
    int max = 0;
    for (int n : nums) max = Math.max(max, n);
    int[] earn = new int[max + 1];
    for (int n : nums) earn[n] += n;  // total earn for picking value n
    // Now it's House Robber on earn[] (can't pick adjacent values)
    int prev2 = 0, prev1 = 0;
    for (int i = 0; i <= max; i++) {
        int curr = Math.max(prev1, prev2 + earn[i]);
        prev2 = prev1;
        prev1 = curr;
    }
    return prev1;
}
```

### Visualization
```
House Robber: [2, 7, 9, 3, 1]

Index:  0    1    2    3    4
Value:  2    7    9    3    1
dp:     2    7   11   11   12
             ↑         ↑
           skip 0   skip 2   take: prev2(11)+1=12

Circular [2,3,2]:  max(rob[2,3], rob[3,2]) = max(3, 3) = 3

Delete and Earn [3,4,2]:
earn = [0, 0, 2, 3, 4]  → House Robber → max(skip 3 take 4=4, take 3 skip 4=3...) 
Actually: prev2=0,prev1=0 → i=2: max(0,0+2)=2 → i=3: max(2,0+3)=3 → i=4: max(3,2+4)=6
Answer: 6
```

### Complexity
- Time: O(n), Space: O(1)

---

## 3. Longest Increasing Subsequence (LIS)

### Signal
- "Longest subsequence with monotonic property"
- "Minimum number of increasing subsequences to cover"
- Problems: LIS, Russian Doll Envelopes, Number of LIS

### Key Recurrence
```
O(n²): dp[i] = max(dp[j] + 1) for all j < i where nums[j] < nums[i]
O(n log n): maintain tails[] array, binary search for position
```

### Template (Java)

```java
// O(n²) DP approach
public int lengthOfLIS_DP(int[] nums) {
    int n = nums.length;
    int[] dp = new int[n];
    Arrays.fill(dp, 1);
    int maxLen = 1;
    for (int i = 1; i < n; i++) {
        for (int j = 0; j < i; j++) {
            if (nums[j] < nums[i]) {
                dp[i] = Math.max(dp[i], dp[j] + 1);
            }
        }
        maxLen = Math.max(maxLen, dp[i]);
    }
    return maxLen;
}

// O(n log n) Patience Sorting approach
public int lengthOfLIS(int[] nums) {
    List<Integer> tails = new ArrayList<>();  // tails[i] = smallest tail of IS of length i+1
    for (int num : nums) {
        int pos = Collections.binarySearch(tails, num);
        if (pos < 0) pos = -(pos + 1);
        if (pos == tails.size()) {
            tails.add(num);
        } else {
            tails.set(pos, num);
        }
    }
    return tails.size();
}
```

### Visualization - Patience Sorting Trace
```
nums = [10, 9, 2, 5, 3, 7, 101, 18]

Step-by-step tails[] evolution:
  Process 10:  tails = [10]
  Process 9:   tails = [9]          (replace 10, 9 < 10)
  Process 2:   tails = [2]          (replace 9)
  Process 5:   tails = [2, 5]       (extend)
  Process 3:   tails = [2, 3]       (replace 5, better tail for len 2)
  Process 7:   tails = [2, 3, 7]    (extend)
  Process 101: tails = [2, 3, 7, 101] (extend)
  Process 18:  tails = [2, 3, 7, 18]  (replace 101)

Answer: len(tails) = 4
Note: tails is NOT the actual LIS, just the optimal tails.
Actual LIS example: [2, 3, 7, 101] or [2, 3, 7, 18] or [2, 5, 7, 101]

WHY this works:
- tails[i] = smallest possible last element for an IS of length i+1
- Always sorted → binary search works
- Replacing preserves future extensibility
```

### Complexity
- O(n²) approach: Time O(n²), Space O(n)
- O(n log n) approach: Time O(n log n), Space O(n)

---

## 4. 0/1 Knapsack

### Signal
- Each item can be used **at most once**
- Maximize value within capacity, or check if subset achieves target
- Problems: 0/1 Knapsack, Partition Equal Subset Sum, Target Sum

### Key Recurrence
```
dp[i][w] = max(dp[i-1][w], dp[i-1][w - wt[i]] + val[i])
              ↑ skip item i    ↑ take item i (use previous row!)
```

### Why Iterate Backwards (1D optimization)
```
2D: dp[i][w] depends on dp[i-1][w] and dp[i-1][w-wt[i]]
    → needs PREVIOUS row values

1D: if we iterate w LEFT to RIGHT:
    dp[w-wt[i]] might already be updated (item i used twice!) ← WRONG

    if we iterate w RIGHT to LEFT:
    dp[w-wt[i]] still has previous iteration value ← CORRECT

    for w = W down to wt[i]:
        dp[w] = max(dp[w], dp[w - wt[i]] + val[i])
```

### Template (Java)

```java
// Classic 0/1 Knapsack (1D optimized)
public int knapsack(int[] weights, int[] values, int W) {
    int[] dp = new int[W + 1];
    for (int i = 0; i < weights.length; i++) {
        for (int w = W; w >= weights[i]; w--) {  // BACKWARDS!
            dp[w] = Math.max(dp[w], dp[w - weights[i]] + values[i]);
        }
    }
    return dp[W];
}

// Partition Equal Subset Sum - can we split into two equal halves?
public boolean canPartition(int[] nums) {
    int sum = 0;
    for (int n : nums) sum += n;
    if (sum % 2 != 0) return false;
    int target = sum / 2;
    boolean[] dp = new boolean[target + 1];
    dp[0] = true;
    for (int num : nums) {
        for (int w = target; w >= num; w--) {  // BACKWARDS
            dp[w] = dp[w] || dp[w - num];
        }
    }
    return dp[target];
}

// Target Sum: assign + or - to each num to reach target
public int findTargetSumWays(int[] nums, int target) {
    // sum(P) - sum(N) = target, sum(P) + sum(N) = totalSum
    // → sum(P) = (target + totalSum) / 2  → count subsets with this sum
    int sum = 0;
    for (int n : nums) sum += n;
    if ((sum + target) % 2 != 0 || sum + target < 0) return 0;
    int subsetSum = (sum + target) / 2;
    int[] dp = new int[subsetSum + 1];
    dp[0] = 1;
    for (int num : nums) {
        for (int w = subsetSum; w >= num; w--) {
            dp[w] += dp[w - num];
        }
    }
    return dp[subsetSum];
}
```

### Visualization
```
0/1 Knapsack: items=[(wt=1,val=1),(wt=3,val=4),(wt=4,val=5)], W=7

2D table (i=item index, w=capacity):
     w: 0  1  2  3  4  5  6  7
i=0:    0  1  1  1  1  1  1  1
i=1:    0  1  1  4  5  5  5  5
i=2:    0  1  1  4  5  6  6  9  ← answer: 9

1D iteration (backwards) for item(wt=3,val=4):
  dp = [0, 1, 1, 1, 1, 1, 1, 1]  (after item 0)
  w=7: dp[7] = max(dp[7]=1, dp[4]+4=5) = 5
  w=6: dp[6] = max(dp[6]=1, dp[3]+4=5) = 5
  w=5: dp[5] = max(dp[5]=1, dp[2]+4=5) = 5
  w=4: dp[4] = max(dp[4]=1, dp[1]+4=5) = 5
  w=3: dp[3] = max(dp[3]=1, dp[0]+4=4) = 4
  dp = [0, 1, 1, 4, 5, 5, 5, 5]
```

### Complexity
- Time: O(n * W), Space: O(W) with 1D optimization

---

## 5. Unbounded Knapsack

### Signal
- Items can be used **unlimited times**
- "Minimum coins to make amount", "Number of combinations"
- Problems: Coin Change, Coin Change II, Rod Cutting

### Why Iterate Forwards
```
0/1: backwards ensures each item used once (reads stale values)
Unbounded: forwards allows item reuse (reads updated values = using item again)

for w = wt[i] to W:           // FORWARDS!
    dp[w] = max(dp[w], dp[w - wt[i]] + val[i])
    // dp[w-wt[i]] may already include item i → that's desired!
```

### Template (Java)

```java
// Coin Change - minimum coins to make amount
public int coinChange(int[] coins, int amount) {
    int[] dp = new int[amount + 1];
    Arrays.fill(dp, amount + 1);  // "infinity"
    dp[0] = 0;
    for (int i = 1; i <= amount; i++) {       // iterate by amount
        for (int coin : coins) {
            if (coin <= i) {
                dp[i] = Math.min(dp[i], dp[i - coin] + 1);
            }
        }
    }
    return dp[amount] > amount ? -1 : dp[amount];
}

// Coin Change II - count combinations (not permutations!)
// IMPORTANT: outer loop = coins, inner loop = amount → combinations
//            outer loop = amount, inner loop = coins → permutations
public int change(int amount, int[] coins) {
    int[] dp = new int[amount + 1];
    dp[0] = 1;
    for (int coin : coins) {                  // coins outer → combinations
        for (int w = coin; w <= amount; w++) { // FORWARDS
            dp[w] += dp[w - coin];
        }
    }
    return dp[amount];
}

// Rod Cutting - maximize revenue
public int cutRod(int[] prices, int n) {
    // prices[i] = price of rod of length i+1
    int[] dp = new int[n + 1];
    for (int len = 1; len <= n; len++) {
        for (int cut = 1; cut <= len; cut++) {
            dp[len] = Math.max(dp[len], prices[cut - 1] + dp[len - cut]);
        }
    }
    return dp[n];
}
```

### Visualization
```
Coin Change: coins=[1,2,5], amount=11

dp: [0, 1, 1, 2, 2, 1, 2, 2, 3, 3, 2, 3]
     0  1  2  3  4  5  6  7  8  9  10 11
                                        ↑ answer: 3 (5+5+1)

Coin Change II (combinations): coins=[1,2,5], amount=5

After coin=1: [1, 1, 1, 1, 1, 1]  (all 1s)
After coin=2: [1, 1, 2, 2, 3, 3]  (add 2-combos)
After coin=5: [1, 1, 2, 2, 3, 4]  (add 5-combo)
Answer: 4 ways → {1,1,1,1,1}, {1,1,1,2}, {1,2,2}, {5}

WHY coins-outer gives COMBINATIONS:
- Each coin considered once as a "phase"
- Within phase, same coin reusable (forwards)
- But coin=2 phase never revisits coin=1 decisions → no duplicate {1,2} vs {2,1}
```

### Complexity
- Time: O(n * amount), Space: O(amount)

---

## 6. Two-String DP

### Signal
- Two strings/sequences as input
- "Transform A to B", "Common subsequence", "Match pattern"
- Problems: LCS, Edit Distance, Distinct Subsequences, Interleaving String, Wildcard/Regex Matching

### Key Recurrences
```
LCS:     dp[i][j] = dp[i-1][j-1]+1          if match
                   = max(dp[i-1][j], dp[i][j-1])  otherwise

Edit:    dp[i][j] = dp[i-1][j-1]            if match
                   = 1 + min(dp[i-1][j],     // delete
                             dp[i][j-1],     // insert
                             dp[i-1][j-1])   // replace
```

### Template (Java)

```java
// Longest Common Subsequence
public int longestCommonSubsequence(String text1, String text2) {
    int m = text1.length(), n = text2.length();
    int[] dp = new int[n + 1];  // space optimized
    for (int i = 1; i <= m; i++) {
        int prev = 0;  // dp[i-1][j-1]
        for (int j = 1; j <= n; j++) {
            int temp = dp[j];
            if (text1.charAt(i - 1) == text2.charAt(j - 1)) {
                dp[j] = prev + 1;
            } else {
                dp[j] = Math.max(dp[j], dp[j - 1]);
            }
            prev = temp;
        }
    }
    return dp[n];
}

// Edit Distance (Levenshtein)
public int minDistance(String word1, String word2) {
    int m = word1.length(), n = word2.length();
    int[] dp = new int[n + 1];
    for (int j = 0; j <= n; j++) dp[j] = j;
    for (int i = 1; i <= m; i++) {
        int prev = dp[0];
        dp[0] = i;
        for (int j = 1; j <= n; j++) {
            int temp = dp[j];
            if (word1.charAt(i - 1) == word2.charAt(j - 1)) {
                dp[j] = prev;
            } else {
                dp[j] = 1 + Math.min(prev, Math.min(dp[j], dp[j - 1]));
            }
            prev = temp;
        }
    }
    return dp[n];
}

// Distinct Subsequences - count subsequences of s that equal t
public int numDistinct(String s, String t) {
    int m = s.length(), n = t.length();
    int[] dp = new int[n + 1];
    dp[0] = 1;
    for (int i = 1; i <= m; i++) {
        for (int j = n; j >= 1; j--) {  // backwards to not overwrite
            if (s.charAt(i - 1) == t.charAt(j - 1)) {
                dp[j] += dp[j - 1];
            }
        }
    }
    return dp[n];
}

// Interleaving String
public boolean isInterleave(String s1, String s2, String s3) {
    int m = s1.length(), n = s2.length();
    if (m + n != s3.length()) return false;
    boolean[] dp = new boolean[n + 1];
    for (int i = 0; i <= m; i++) {
        for (int j = 0; j <= n; j++) {
            if (i == 0 && j == 0) { dp[j] = true; continue; }
            boolean fromS1 = i > 0 && dp[j] && s1.charAt(i-1) == s3.charAt(i+j-1);
            boolean fromS2 = j > 0 && dp[j-1] && s2.charAt(j-1) == s3.charAt(i+j-1);
            dp[j] = fromS1 || fromS2;
        }
    }
    return dp[n];
}

// Wildcard Matching ('?' matches one, '*' matches any sequence)
public boolean isMatch(String s, String p) {
    int m = s.length(), n = p.length();
    boolean[] dp = new boolean[n + 1];
    dp[0] = true;
    for (int j = 1; j <= n; j++) dp[j] = p.charAt(j-1) == '*' && dp[j-1];
    for (int i = 1; i <= m; i++) {
        boolean prev = dp[0];
        dp[0] = false;
        for (int j = 1; j <= n; j++) {
            boolean temp = dp[j];
            if (p.charAt(j-1) == '*') {
                dp[j] = dp[j] || dp[j-1];  // * matches empty or extends
            } else if (p.charAt(j-1) == '?' || s.charAt(i-1) == p.charAt(j-1)) {
                dp[j] = prev;
            } else {
                dp[j] = false;
            }
            prev = temp;
        }
    }
    return dp[n];
}

// Regex Matching ('.' matches one, '*' means zero or more of preceding)
public boolean isMatchRegex(String s, String p) {
    int m = s.length(), n = p.length();
    boolean[][] dp = new boolean[m + 1][n + 1];
    dp[0][0] = true;
    for (int j = 2; j <= n; j++) {
        if (p.charAt(j-1) == '*') dp[0][j] = dp[0][j-2];  // x* matches empty
    }
    for (int i = 1; i <= m; i++) {
        for (int j = 1; j <= n; j++) {
            char pc = p.charAt(j-1);
            if (pc == '*') {
                char prev = p.charAt(j-2);
                dp[i][j] = dp[i][j-2];  // zero occurrences
                if (prev == '.' || prev == s.charAt(i-1)) {
                    dp[i][j] |= dp[i-1][j];  // one+ occurrences
                }
            } else if (pc == '.' || pc == s.charAt(i-1)) {
                dp[i][j] = dp[i-1][j-1];
            }
        }
    }
    return dp[m][n];
}
```

### Visualization
```
Edit Distance: "horse" → "ros"

      ""  r  o  s
  ""   0  1  2  3
  h    1  1  2  3
  o    2  2  1  2
  r    3  2  2  2
  s    4  3  3  2  ← answer
  e    5  4  4  3  ← answer: 3

Operations: horse → rorse (replace h→r) → rose (delete r) → ros (delete e)
```

### Complexity
- Time: O(m * n), Space: O(n) with 1D optimization (except Regex which needs 2D or careful handling)

---

## 7. Grid DP

### Signal
- 2D grid/matrix traversal
- "Number of paths", "Minimum cost path", "Largest square"
- Movement typically right/down only

### Key Recurrences
```
Unique Paths: dp[i][j] = dp[i-1][j] + dp[i][j-1]
Min Path Sum: dp[i][j] = grid[i][j] + min(dp[i-1][j], dp[i][j-1])
Maximal Square: dp[i][j] = min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1]) + 1  (if '1')
```

### Template (Java)

```java
// Unique Paths (with obstacles)
public int uniquePathsWithObstacles(int[][] grid) {
    int n = grid[0].length;
    int[] dp = new int[n];
    dp[0] = 1;
    for (int[] row : grid) {
        for (int j = 0; j < n; j++) {
            if (row[j] == 1) { dp[j] = 0; continue; }
            if (j > 0) dp[j] += dp[j - 1];
        }
    }
    return dp[n - 1];
}

// Minimum Path Sum
public int minPathSum(int[][] grid) {
    int m = grid.length, n = grid[0].length;
    int[] dp = new int[n];
    dp[0] = grid[0][0];
    for (int j = 1; j < n; j++) dp[j] = dp[j-1] + grid[0][j];
    for (int i = 1; i < m; i++) {
        dp[0] += grid[i][0];
        for (int j = 1; j < n; j++) {
            dp[j] = grid[i][j] + Math.min(dp[j], dp[j-1]);
        }
    }
    return dp[n - 1];
}

// Maximal Square
public int maximalSquare(char[][] matrix) {
    int m = matrix.length, n = matrix[0].length;
    int[] dp = new int[n + 1];
    int maxSide = 0, prev = 0;
    for (int i = 1; i <= m; i++) {
        for (int j = 1; j <= n; j++) {
            int temp = dp[j];
            if (matrix[i-1][j-1] == '1') {
                dp[j] = Math.min(Math.min(dp[j], dp[j-1]), prev) + 1;
                maxSide = Math.max(maxSide, dp[j]);
            } else {
                dp[j] = 0;
            }
            prev = temp;
        }
        prev = 0;
    }
    return maxSide * maxSide;
}
```

### Visualization
```
Maximal Square:
  1 0 1 0 0         dp:
  1 0 1 1 1         1 0 1 0 0
  1 1 1 1 1         1 0 1 1 1
  1 0 0 1 0         1 1 1 2 2
                    1 0 0 1 0
                          ↑
                    max side = 2, area = 4

Why min(top, left, diag)+1?
  If any neighbor square is smaller, current square is limited by it.
  ┌──┬──┐
  │DG│ T│   DG=diagonal, T=top, L=left
  ├──┼──┤   dp[i][j] = min(DG,T,L) + 1
  │ L│ ?│
  └──┴──┘
```

### Complexity
- Time: O(m * n), Space: O(n)

---

## 8. Interval DP

### Signal
- "Merge elements optimally", "Cost of operations on a range"
- Subproblems are contiguous subarrays/ranges
- O(n³) typical
- Problems: Burst Balloons, Matrix Chain Multiplication, Palindrome Partitioning II, Stone Game

### Key Recurrence
```
dp[i][j] = optimize over all split points k in [i, j]:
            dp[i][k] (op) dp[k+1][j] (op) cost(i, k, j)
```

### Template (Java)

```java
// Burst Balloons - maximize coins from bursting all balloons
public int maxCoins(int[] nums) {
    int n = nums.length;
    int[] arr = new int[n + 2];  // pad with 1s
    arr[0] = arr[n + 1] = 1;
    for (int i = 0; i < n; i++) arr[i + 1] = nums[i];
    int[][] dp = new int[n + 2][n + 2];
    // dp[i][j] = max coins from bursting all balloons in (i, j) exclusive
    for (int len = 1; len <= n; len++) {
        for (int i = 1; i + len - 1 <= n; i++) {
            int j = i + len - 1;
            for (int k = i; k <= j; k++) {  // k is LAST balloon burst in [i,j]
                dp[i][j] = Math.max(dp[i][j],
                    dp[i][k-1] + arr[i-1] * arr[k] * arr[j+1] + dp[k+1][j]);
            }
        }
    }
    return dp[1][n];
}

// Matrix Chain Multiplication - minimum scalar multiplications
public int matrixChainOrder(int[] dims) {
    // dims[i-1] x dims[i] = dimensions of matrix i
    int n = dims.length - 1;  // number of matrices
    int[][] dp = new int[n][n];
    for (int len = 2; len <= n; len++) {
        for (int i = 0; i + len - 1 < n; i++) {
            int j = i + len - 1;
            dp[i][j] = Integer.MAX_VALUE;
            for (int k = i; k < j; k++) {
                int cost = dp[i][k] + dp[k+1][j] + dims[i] * dims[k+1] * dims[j+1];
                dp[i][j] = Math.min(dp[i][j], cost);
            }
        }
    }
    return dp[0][n - 1];
}

// Palindrome Partitioning II - minimum cuts for all palindrome substrings
public int minCut(String s) {
    int n = s.length();
    boolean[][] isPalin = new boolean[n][n];
    for (int i = n - 1; i >= 0; i--) {
        for (int j = i; j < n; j++) {
            isPalin[i][j] = s.charAt(i) == s.charAt(j) && (j - i <= 2 || isPalin[i+1][j-1]);
        }
    }
    int[] dp = new int[n];  // dp[i] = min cuts for s[0..i]
    Arrays.fill(dp, Integer.MAX_VALUE);
    for (int i = 0; i < n; i++) {
        if (isPalin[0][i]) { dp[i] = 0; continue; }
        for (int j = 1; j <= i; j++) {
            if (isPalin[j][i]) dp[i] = Math.min(dp[i], dp[j-1] + 1);
        }
    }
    return dp[n - 1];
}

// Stone Game (Alex vs Lee, pick from ends)
public boolean stoneGame(int[] piles) {
    int n = piles.length;
    int[][] dp = new int[n][n];  // dp[i][j] = max score diff (current player - opponent)
    for (int i = 0; i < n; i++) dp[i][i] = piles[i];
    for (int len = 2; len <= n; len++) {
        for (int i = 0; i + len - 1 < n; i++) {
            int j = i + len - 1;
            dp[i][j] = Math.max(piles[i] - dp[i+1][j], piles[j] - dp[i][j-1]);
        }
    }
    return dp[0][n-1] > 0;
}
```

### Visualization
```
Burst Balloons: [3, 1, 5, 8]
Padded: [1, 3, 1, 5, 8, 1]

dp[i][j] filled by increasing length:
len=1: dp[1][1]=3, dp[2][2]=3, dp[3][3]=40, dp[4][4]=40
len=2: dp[1][2]=max(1*3*5+1*1*5, 1*1*5+1*3*5)=...
...
Final: dp[1][4] = 167

Key insight: k = last balloon to burst in range.
When k is last, boundaries are arr[i-1] and arr[j+1] (still exist).

Interval DP iteration pattern:
  for len = 1 to n:        ← increasing length
    for i = start positions:
      j = i + len - 1
      for k = split points:
```

### Complexity
- Time: O(n³), Space: O(n²)

---

## 9. State Machine DP (Stock Buy/Sell)

### Signal
- Multiple states with defined transitions
- "Cooldown period", "Transaction limit", "Fee per transaction"
- Naturally modeled as state diagram

### State Diagrams

```
Stock I (1 transaction):
  ┌──────┐  buy   ┌──────┐  sell  ┌──────┐
  │ REST ├───────→ │ HOLD ├──────→ │ SOLD │
  └──────┘        └──────┘        └──────┘

Stock II (unlimited):
  ┌──────┐  buy   ┌──────┐
  │ REST │←──────→│ HOLD │
  └──┬───┘  sell  └──────┘
     │  ↑
     └──┘ (wait)

Stock with Cooldown:
  ┌──────┐  buy   ┌──────┐  sell  ┌──────────┐
  │ REST │←───────│ HOLD │──────→ │ COOLDOWN │
  │      ├───────→│      │        │          │
  └──┬───┘        └──┬───┘        └────┬─────┘
     │↑(wait)        │↑(wait)          │ (must wait 1 day)
     └┘              └┘                │
     ↑                                 │
     └─────────────────────────────────┘

Stock III/IV (k transactions):
  States: (transaction_count, holding/not_holding)
```

### Template (Java)

```java
// Stock I - at most 1 transaction
public int maxProfit1(int[] prices) {
    int minPrice = Integer.MAX_VALUE, maxProfit = 0;
    for (int p : prices) {
        minPrice = Math.min(minPrice, p);
        maxProfit = Math.max(maxProfit, p - minPrice);
    }
    return maxProfit;
}

// Stock II - unlimited transactions
public int maxProfit2(int[] prices) {
    int profit = 0;
    for (int i = 1; i < prices.length; i++) {
        if (prices[i] > prices[i-1]) profit += prices[i] - prices[i-1];
    }
    return profit;
}

// Stock III - at most 2 transactions
public int maxProfit3(int[] prices) {
    int buy1 = Integer.MIN_VALUE, sell1 = 0;
    int buy2 = Integer.MIN_VALUE, sell2 = 0;
    for (int p : prices) {
        buy1 = Math.max(buy1, -p);
        sell1 = Math.max(sell1, buy1 + p);
        buy2 = Math.max(buy2, sell1 - p);
        sell2 = Math.max(sell2, buy2 + p);
    }
    return sell2;
}

// Stock IV - at most k transactions
public int maxProfit4(int k, int[] prices) {
    if (k >= prices.length / 2) return maxProfit2(prices); // unlimited
    int[] buy = new int[k + 1], sell = new int[k + 1];
    Arrays.fill(buy, Integer.MIN_VALUE);
    for (int p : prices) {
        for (int j = 1; j <= k; j++) {
            buy[j] = Math.max(buy[j], sell[j-1] - p);
            sell[j] = Math.max(sell[j], buy[j] + p);
        }
    }
    return sell[k];
}

// Stock with Cooldown (must wait 1 day after selling)
public int maxProfitCooldown(int[] prices) {
    int hold = Integer.MIN_VALUE, sold = 0, rest = 0;
    for (int p : prices) {
        int prevSold = sold;
        sold = hold + p;          // sell today
        hold = Math.max(hold, rest - p);  // buy today (from rest, not sold)
        rest = Math.max(rest, prevSold);  // cooldown complete
    }
    return Math.max(sold, rest);
}

// Stock with Transaction Fee
public int maxProfitFee(int[] prices, int fee) {
    int hold = -prices[0], cash = 0;
    for (int i = 1; i < prices.length; i++) {
        hold = Math.max(hold, cash - prices[i]);
        cash = Math.max(cash, hold + prices[i] - fee);
    }
    return cash;
}
```

### Visualization
```
Cooldown: prices = [1, 2, 3, 0, 2]

Day:     0      1      2      3      4
hold:   -1     -1     -1      1      1
sold:   -∞      1      2     -1      3  ← answer
rest:    0      0      1      2      2

Day 0: buy at 1
Day 1: hold
Day 2: sell at 3 (profit 2)
Day 3: cooldown (rest)
Day 4: buy at 0, sell at 2 → total profit = 2 + 2... wait
Actually: sell day2(+2), cooldown day3, buy day3... 
rest allows buy: hold = max(1, rest(2)-0) = 2... 
Final: sold=hold(1)+2=3 ← Answer: 3
```

### Complexity
- Time: O(n) for fixed states, O(n*k) for k transactions
- Space: O(1) for fixed states, O(k) for k transactions

---

## 10. Tree DP

### Signal
- Optimal value computation on tree structure
- Each node makes take/skip decision
- DFS returns state pair
- Problems: Binary Tree Max Path Sum, House Robber III, Tree Diameter

### Template (Java)

```java
// Binary Tree Maximum Path Sum
int maxSum = Integer.MIN_VALUE;
public int maxPathSum(TreeNode root) {
    dfs(root);
    return maxSum;
}
private int dfs(TreeNode node) {
    if (node == null) return 0;
    int left = Math.max(0, dfs(node.left));   // ignore negative paths
    int right = Math.max(0, dfs(node.right));
    maxSum = Math.max(maxSum, left + node.val + right);  // path through node
    return node.val + Math.max(left, right);  // extend one side upward
}

// House Robber III (tree)
public int rob(TreeNode root) {
    int[] res = robDFS(root);
    return Math.max(res[0], res[1]);
}
private int[] robDFS(TreeNode node) {
    if (node == null) return new int[]{0, 0};
    int[] left = robDFS(node.left);
    int[] right = robDFS(node.right);
    // [0] = max if we DON'T rob this node
    // [1] = max if we DO rob this node
    int skip = Math.max(left[0], left[1]) + Math.max(right[0], right[1]);
    int take = node.val + left[0] + right[0];
    return new int[]{skip, take};
}

// Tree Diameter (longest path between any two nodes)
int diameter = 0;
public int diameterOfBinaryTree(TreeNode root) {
    height(root);
    return diameter;
}
private int height(TreeNode node) {
    if (node == null) return 0;
    int left = height(node.left);
    int right = height(node.right);
    diameter = Math.max(diameter, left + right);
    return 1 + Math.max(left, right);
}
```

### Visualization
```
House Robber III:
        3
       / \
      2    3
       \    \
        3    1

DFS returns [skip, take]:
  Node 3 (left-leaf): [0, 3]
  Node 1 (leaf):      [0, 1]
  Node 2:  skip=max(0,3)=3, take=2+0=2   → [3, 2]
  Node 3R: skip=max(0,1)=1, take=3+0=3   → [1, 3]
  Root 3:  skip=max(3,2)+max(1,3)=3+3=6, take=3+3+1=7  → [6, 7]
  Answer: max(6, 7) = 7  (rob root + both grandchildren: 3+3+1=7)
```

### Complexity
- Time: O(n), Space: O(h) where h = tree height (recursion stack)

---

## 11. Bitmask DP

### Signal
- n ≤ 20 (or n ≤ 15 for O(n² * 2^n))
- "Assign n items to n slots", "Visit all nodes", "Optimal subset selection"
- Problems: TSP, Assign Tasks, Can I Win

### Key Recurrence
```
dp[mask] = optimize over all unset bits in mask
TSP: dp[mask][i] = min cost to visit cities in mask, ending at i
```

### Template (Java)

```java
// Travelling Salesman Problem
public int tsp(int[][] dist) {
    int n = dist.length;
    int[][] dp = new int[1 << n][n];
    for (int[] row : dp) Arrays.fill(row, Integer.MAX_VALUE / 2);
    dp[1][0] = 0;  // start at city 0
    for (int mask = 1; mask < (1 << n); mask++) {
        for (int u = 0; u < n; u++) {
            if ((mask & (1 << u)) == 0) continue;  // u not in mask
            for (int v = 0; v < n; v++) {
                if ((mask & (1 << v)) != 0) continue;  // v already visited
                int newMask = mask | (1 << v);
                dp[newMask][v] = Math.min(dp[newMask][v], dp[mask][u] + dist[u][v]);
            }
        }
    }
    int fullMask = (1 << n) - 1;
    int ans = Integer.MAX_VALUE;
    for (int u = 0; u < n; u++) {
        ans = Math.min(ans, dp[fullMask][u] + dist[u][0]);
    }
    return ans;
}

// Can I Win - forced win with optimal play
public boolean canIWin(int maxChoosableInteger, int desiredTotal) {
    if (maxChoosableInteger * (maxChoosableInteger + 1) / 2 < desiredTotal) return false;
    Map<Integer, Boolean> memo = new HashMap<>();
    return canWin(0, desiredTotal, maxChoosableInteger, memo);
}
private boolean canWin(int mask, int remaining, int max, Map<Integer, Boolean> memo) {
    if (memo.containsKey(mask)) return memo.get(mask);
    for (int i = 1; i <= max; i++) {
        if ((mask & (1 << i)) != 0) continue;  // already used
        if (i >= remaining || !canWin(mask | (1 << i), remaining - i, max, memo)) {
            memo.put(mask, true);
            return true;  // I win by picking i (either reach target or opponent loses)
        }
    }
    memo.put(mask, false);
    return false;
}

// Assign Tasks to Workers (minimum cost perfect matching)
public int assignTasks(int[][] cost) {
    int n = cost.length;
    int[] dp = new int[1 << n];
    Arrays.fill(dp, Integer.MAX_VALUE);
    dp[0] = 0;
    for (int mask = 0; mask < (1 << n); mask++) {
        int worker = Integer.bitCount(mask);  // next worker to assign
        if (worker >= n) continue;
        for (int task = 0; task < n; task++) {
            if ((mask & (1 << task)) != 0) continue;
            dp[mask | (1 << task)] = Math.min(dp[mask | (1 << task)],
                                               dp[mask] + cost[worker][task]);
        }
    }
    return dp[(1 << n) - 1];
}
```

### Visualization
```
TSP with 4 cities (0-indexed), bitmask represents visited set:

mask = 0b1011 (cities 0,1,3 visited), current at city 3:
  dp[0b1011][3] = min cost path visiting {0,1,3} ending at 3

Transition: go to city 2 (unvisited)
  dp[0b1111][2] = min(dp[0b1111][2], dp[0b1011][3] + dist[3][2])

Full mask = 0b1111, then add return to start:
  answer = min over all u: dp[0b1111][u] + dist[u][0]

Bit tricks:
  Check bit i set:    (mask >> i) & 1
  Set bit i:          mask | (1 << i)
  Clear bit i:        mask & ~(1 << i)
  Count set bits:     Integer.bitCount(mask)
  Iterate subsets:    for (int s = mask; s > 0; s = (s-1) & mask)
```

### Complexity
- Time: O(n² * 2^n), Space: O(n * 2^n)
- Feasible for n ≤ 20 (2^20 ≈ 1M)

---

## 12. Digit DP

### Signal
- "Count numbers in [L, R] with property P"
- Digit-by-digit construction with tight constraint
- Problems: Count numbers with digit sum = k, no repeated digits, etc.

### Key Recurrence
```
dp(pos, state, tight, started)
  pos    = current digit position (left to right)
  state  = problem-specific (digit sum, last digit, mask, etc.)
  tight  = are we still bounded by the limit?
  started = have we placed a non-zero digit? (for leading zeros)
```

### Template (Java)

```java
// Count numbers in [1, num] with no repeated digits
public int countSpecialNumbers(int n) {
    String digits = String.valueOf(n);
    int len = digits.length();
    // memo[pos][mask][tight]
    Integer[][][] memo = new Integer[len][1 << 10][2];
    return solve(digits, 0, 0, true, false, memo);
}

private int solve(String num, int pos, int mask, boolean tight, boolean started,
                  Integer[][][] memo) {
    if (pos == num.length()) return started ? 1 : 0;
    if (memo[pos][mask][tight ? 1 : 0] != null && started)
        return memo[pos][mask][tight ? 1 : 0];
    
    int limit = tight ? num.charAt(pos) - '0' : 9;
    int count = 0;
    
    for (int d = 0; d <= limit; d++) {
        if (!started && d == 0) {
            count += solve(num, pos + 1, mask, tight && d == limit, false, memo);
        } else if ((mask & (1 << d)) == 0) {  // digit not used
            count += solve(num, pos + 1, mask | (1 << d), tight && d == limit, true, memo);
        }
    }
    
    if (started) memo[pos][mask][tight ? 1 : 0] = count;
    return count;
}

// General template: count numbers in [L, R] with property
// f(R) - f(L-1) where f(X) = count of valid numbers in [0, X]
public int countInRange(int L, int R) {
    return countUpTo(R) - countUpTo(L - 1);
}

// Count numbers ≤ num whose digit sum equals target
public int digitSumCount(int num, int target) {
    String s = String.valueOf(num);
    Integer[][] memo = new Integer[s.length()][target + 1];
    return digitSumDP(s, 0, target, true, memo);
}

private int digitSumDP(String num, int pos, int remaining, boolean tight, Integer[][] memo) {
    if (remaining < 0) return 0;
    if (pos == num.length()) return remaining == 0 ? 1 : 0;
    if (!tight && memo[pos][remaining] != null) return memo[pos][remaining];
    
    int limit = tight ? num.charAt(pos) - '0' : 9;
    int count = 0;
    for (int d = 0; d <= limit; d++) {
        count += digitSumDP(num, pos + 1, remaining - d, tight && d == limit, memo);
    }
    if (!tight) memo[pos][remaining] = count;
    return count;
}
```

### Visualization
```
Count numbers ≤ 325 with digit sum = 5:

                    pos=0 (hundreds)
                    tight=true, limit=3
                   /    |    \      \
                d=0    d=1   d=2    d=3
               tight=F  F    F     tight=T
               
  When d=0 (tight=false): count all 2-digit numbers with sum=5
    → 05,14,23,32,41,50 = 6 numbers
  When d=1: sum remaining=4, 2 more digits
    → 13,22,31,40 → 113,122,131,140 = 4
  When d=2: sum remaining=3
    → 203,212,221,230 = 4
  When d=3 (tight=true): limit next digit = 2
    → need sum=2 in ≤"25": 302,311,320 = 3
    
  Total = 6 + 4 + 4 + 3 = 17 (verify subset)

Key insight: f(R) - f(L-1) converts range query to prefix query.
```

### Complexity
- Time: O(pos * states * 10), Space: O(pos * states)
- Typically O(log(N) * state_space * 10)

---

## Space Optimization Techniques

### 1. Rolling Array (2 rows → constant rows)

```java
// When dp[i] only depends on dp[i-1], keep 2 rows
int[][] dp = new int[2][n];
for (int i = 0; i < m; i++) {
    int cur = i & 1, prev = cur ^ 1;  // alternate 0 and 1
    for (int j = 0; j < n; j++) {
        dp[cur][j] = f(dp[prev][...]);
    }
}
// Answer in dp[(m-1) & 1][...]
```

### 2. 1D from 2D (collapse row dimension)

```java
// Works when dp[i][j] depends only on dp[i-1][j] and dp[i-1][j-1] (or dp[i][j-1])

// Case A: depends on dp[i-1][j] and dp[i][j-1] → iterate LEFT to RIGHT
// (e.g., Unique Paths, LCS)
for (int i = ...) {
    for (int j = left to right) {
        dp[j] = dp[j] + dp[j-1];  // dp[j] has old value (= dp[i-1][j])
    }
}

// Case B: depends on dp[i-1][j] and dp[i-1][j-1] → need 'prev' variable
for (int i = ...) {
    int prev = dp[0]; // save dp[i-1][0] before overwrite
    for (int j = ...) {
        int temp = dp[j];
        dp[j] = f(prev, dp[j], dp[j-1]);
        prev = temp;
    }
}

// Case C: 0/1 Knapsack (dp[i-1][w] and dp[i-1][w-wt]) → iterate RIGHT to LEFT
for (int i = ...) {
    for (int w = W; w >= wt[i]; w--) {
        dp[w] = max(dp[w], dp[w - wt[i]] + val[i]);
    }
}
```

### 3. Summary Table

| Pattern | 2D Size | Optimized | Direction | Trick |
|---|---|---|---|---|
| LCS / Edit Distance | O(m*n) | O(n) | Left→Right | prev variable for diagonal |
| 0/1 Knapsack | O(n*W) | O(W) | Right→Left | Prevents item reuse |
| Unbounded Knapsack | O(n*W) | O(W) | Left→Right | Allows item reuse |
| Grid DP | O(m*n) | O(n) | Left→Right | Row by row |
| LIS | O(n²) | O(n) | Already 1D | tails[] for O(n log n) |
| Interval DP | O(n²) | Cannot reduce | — | Needs random access |
| Bitmask DP | O(2^n * n) | Cannot reduce | — | Already minimal |

---

## Quick Reference: Pattern Selection Flowchart

```
START
  │
  ├─ Is it on a tree? ──────────────────────→ Tree DP
  │
  ├─ Is n ≤ 20 and need all subsets? ───────→ Bitmask DP
  │
  ├─ Count numbers in range with property? ─→ Digit DP
  │
  ├─ Two strings/sequences? ────────────────→ Two-String DP
  │
  ├─ 2D grid traversal? ───────────────────→ Grid DP
  │
  ├─ Merge/split ranges optimally? ────────→ Interval DP
  │
  ├─ Multiple explicit states/transitions? ─→ State Machine DP
  │
  ├─ Items + capacity constraint?
  │    ├─ Each item once? ──────────────────→ 0/1 Knapsack
  │    └─ Unlimited supply? ────────────────→ Unbounded Knapsack
  │
  ├─ Longest monotonic subsequence? ───────→ LIS
  │
  ├─ Adjacent constraint (can't pick neighbors)?→ Skip/Take
  │
  └─ Sequential decisions, few prior states?→ Linear DP (Fibonacci)
```
