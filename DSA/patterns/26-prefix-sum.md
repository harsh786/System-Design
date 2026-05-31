# Pattern 26: Prefix Sum

## Core Concept

Precompute cumulative sums so that any range query becomes O(1) subtraction.

```
Array:      [2,  4,  1,  3,  5]
Index:       0   1   2   3   4

Prefix:  [0, 2,  6,  7, 10, 15]
Index:    0  1   2   3   4   5

Range Sum [1..3] = prefix[4] - prefix[1] = 10 - 2 = 8
                 = arr[1] + arr[2] + arr[3] = 4+1+3 = 8

Visual:
         prefix[0]   prefix[l]         prefix[r+1]
            |           |                   |
            v           v                   v
prefix: [0, 2, 6, 7, 10, 15]
                 |________|
                  sum(l..r) = prefix[r+1] - prefix[l]
```

**Key Identity:** `sum(l, r) = prefix[r+1] - prefix[l]`

---

## Decision Flowchart

```
Need aggregate (sum/xor/count) over subarrays?
│
├─ Fixed-size window? ──────────────────────> Sliding Window
│
├─ Variable window, all positives, 
│  find min/max length? ───────────────────> Sliding Window (two pointers)
│
├─ Count subarrays with exact sum/remainder?──> Prefix Sum + HashMap
│
├─ Range sum queries on static array? ─────> Prefix Sum Array
│
├─ Range updates + final read? ────────────> Difference Array
│
├─ 2D region queries? ─────────────────────> 2D Prefix Sum
│
└─ XOR over range? ────────────────────────> Prefix XOR
```

**Prefix Sum vs Sliding Window:**
| Criteria | Prefix Sum + Map | Sliding Window |
|----------|-----------------|----------------|
| Array has negatives | Yes | No (breaks monotonicity) |
| Count exact sum subarrays | Yes | Awkward |
| All positives, find length | Possible but overkill | Preferred |
| Need O(1) space | No (uses map) | Yes |

---

## Pattern 1: Basic 1D Prefix Sum (Range Sum Query)

### Signal
- Multiple range sum queries on immutable array
- LC 303: Range Sum Query - Immutable

### Template

```java
class NumArray {
    private int[] prefix;

    public NumArray(int[] nums) {
        prefix = new int[nums.length + 1];
        for (int i = 0; i < nums.length; i++) {
            prefix[i + 1] = prefix[i] + nums[i];
        }
    }

    // sum of nums[left..right] inclusive
    public int sumRange(int left, int right) {
        return prefix[right + 1] - prefix[left];
    }
}
```

### Complexity
- Build: O(n) time, O(n) space
- Query: O(1) time

---

## Pattern 2: Subarray Sum Equals K

### Signal
- Count subarrays with sum exactly K
- Array may contain negatives (sliding window won't work)
- LC 560

### Key Insight

If `prefix[j] - prefix[i] = k`, then subarray `(i, j]` has sum k.
So for each `j`, count how many earlier prefix values equal `prefix[j] - k`.

```
prefix[j] - prefix[i] = k
=> prefix[i] = prefix[j] - k

Use HashMap: {prefix_value -> count of times seen}
```

### Template

```java
public int subarraySum(int[] nums, int k) {
    Map<Integer, Integer> prefixCount = new HashMap<>();
    prefixCount.put(0, 1); // empty prefix
    int sum = 0, count = 0;

    for (int num : nums) {
        sum += num;
        count += prefixCount.getOrDefault(sum - k, 0);
        prefixCount.merge(sum, 1, Integer::sum);
    }
    return count;
}
```

### Visualization

```
nums = [1, 2, 3, -1, 1], k = 3

Step-by-step:
i=0: sum=1, need sum-k=-2, map={0:1,1:1}, count=0
i=1: sum=3, need sum-k=0,  map={0:1,1:1,3:1}, count=1  -> [1,2]
i=2: sum=6, need sum-k=3,  map={...,6:1}, count=2       -> [1,2,3] wait no, [3]? 
     Actually prefix=3 seen once, so subarray (1,2] = {3} yes
i=3: sum=5, need sum-k=2,  not found, count=2
i=4: sum=6, need sum-k=3,  prefix=3 seen once, count=3  -> [3,-1,1]

Answer: 3  (subarrays: [1,2], [3], [3,-1,1])
```

### Complexity
- O(n) time, O(n) space

---

## Pattern 3: Continuous Subarray Sum (Mod K)

### Signal
- Find if subarray of length >= 2 has sum divisible by k
- LC 523

### Key Insight

If `prefix[j] % k == prefix[i] % k` and `j - i >= 2`, then `sum(i+1..j)` is divisible by k.

Store first index where each remainder was seen.

### Template

```java
public boolean checkSubarraySum(int[] nums, int k) {
    Map<Integer, Integer> modIndex = new HashMap<>();
    modIndex.put(0, -1); // empty prefix at index -1
    int sum = 0;

    for (int i = 0; i < nums.length; i++) {
        sum += nums[i];
        int mod = sum % k;
        if (mod < 0) mod += k; // handle negative mods

        if (modIndex.containsKey(mod)) {
            if (i - modIndex.get(mod) >= 2) return true;
        } else {
            modIndex.put(mod, i);
        }
    }
    return false;
}
```

### Complexity
- O(n) time, O(min(n, k)) space

---

## Pattern 4: Subarray Sum Divisible by K

### Signal
- Count subarrays whose sum is divisible by k
- LC 974

### Key Insight

Same remainder logic as Pattern 3 but count all pairs with same mod.
If a remainder `r` has been seen `c` times, any new occurrence can pair with all `c` previous ones.

### Template

```java
public int subarraysDivByK(int[] nums, int k) {
    Map<Integer, Integer> modCount = new HashMap<>();
    modCount.put(0, 1);
    int sum = 0, count = 0;

    for (int num : nums) {
        sum += num;
        int mod = ((sum % k) + k) % k; // always non-negative
        count += modCount.getOrDefault(mod, 0);
        modCount.merge(mod, 1, Integer::sum);
    }
    return count;
}
```

### Complexity
- O(n) time, O(k) space

---

## Pattern 5: 2D Prefix Sum

### Signal
- Multiple region sum queries on immutable matrix
- LC 304: Range Sum Query 2D - Immutable

### Inclusion-Exclusion Formula

```
Build:
  P[i][j] = matrix[i-1][j-1] + P[i-1][j] + P[i][j-1] - P[i-1][j-1]

Query sum of region (r1,c1) to (r2,c2):
  sum = P[r2+1][c2+1] - P[r1][c2+1] - P[r2+1][c1] + P[r1][c1]
```

### Visualization

```
Inclusion-Exclusion for Query:

  (0,0)─────────────────────────
    │          │                │
    │    A     │       B        │
    │          │                │
    ├──────────(r1,c1)──────────│
    │          │ ////////////// │
    │    C     │ /// TARGET /// │
    │          │ ////////////// │
    │──────────│────────(r2,c2) │
    └───────────────────────────┘

  TARGET = Total - B - C + A
         = P[r2+1][c2+1] - P[r1][c2+1] - P[r2+1][c1] + P[r1][c1]

  (We add A back because it was subtracted twice)
```

### Template

```java
class NumMatrix {
    private int[][] prefix;

    public NumMatrix(int[][] matrix) {
        int m = matrix.length, n = matrix[0].length;
        prefix = new int[m + 1][n + 1];
        for (int i = 1; i <= m; i++) {
            for (int j = 1; j <= n; j++) {
                prefix[i][j] = matrix[i-1][j-1]
                    + prefix[i-1][j] + prefix[i][j-1] - prefix[i-1][j-1];
            }
        }
    }

    public int sumRegion(int r1, int c1, int r2, int c2) {
        return prefix[r2+1][c2+1] - prefix[r1][c2+1]
             - prefix[r2+1][c1] + prefix[r1][c1];
    }
}
```

### Complexity
- Build: O(m*n) time and space
- Query: O(1)

---

## Pattern 6: Product of Array Except Self

### Signal
- Compute product of all elements except self without division
- LC 238

### Key Insight

`result[i] = prefixProduct[0..i-1] * suffixProduct[i+1..n-1]`

### Template

```java
public int[] productExceptSelf(int[] nums) {
    int n = nums.length;
    int[] result = new int[n];

    // prefix product (left to right)
    result[0] = 1;
    for (int i = 1; i < n; i++) {
        result[i] = result[i - 1] * nums[i - 1];
    }

    // suffix product (right to left), multiply in
    int suffix = 1;
    for (int i = n - 1; i >= 0; i--) {
        result[i] *= suffix;
        suffix *= nums[i];
    }
    return result;
}
```

### Visualization

```
nums:    [1, 2, 3, 4]

prefix:  [1, 1, 2, 6]   (product of everything to the left)
suffix:  [24,12,4, 1]   (product of everything to the right)
result:  [24,12,8, 6]   (prefix[i] * suffix[i])
```

### Complexity
- O(n) time, O(1) extra space (result array not counted)

---

## Pattern 7: Difference Array / Range Addition

### Signal
- Multiple range increment operations, then read final array
- LC 370: Range Addition
- LC 1109: Corporate Flight Bookings

### Key Insight

Instead of updating every element in range [l, r], mark:
- `diff[l] += val`
- `diff[r+1] -= val`

Then prefix sum of diff gives the final array.

### Visualization (Trace)

```
Initial: [0, 0, 0, 0, 0]  (length 5)
Operations: add 2 to [1,3], add 3 to [2,4], add -1 to [0,1]

Difference array updates:
  add 2 to [1,3]:  diff = [0, +2, 0, 0, -2]
  add 3 to [2,4]:  diff = [0, +2, +3, 0, -2]  (r+1=5 is out of bounds, skip)
  add -1 to [0,1]: diff = [-1, +2, +4, 0, -2]  (diff[0]-=1 wait...)

Let me redo carefully:
  diff = [0, 0, 0, 0, 0]
  
  add 2 to [1,3]:  diff[1]+=2, diff[4]-=2  => [0, 2, 0, 0, -2]
  add 3 to [2,4]:  diff[2]+=3, diff[5]-=3  => [0, 2, 3, 0, -2]  (index 5 ignored)
  add -1 to [0,1]: diff[0]-=1, diff[2]+=1  => [-1, 2, 4, 0, -2]

Prefix sum of diff:
  [-1, 1, 5, 5, 3]

Verify: 
  index 0: -1 (only [-1 from op3])
  index 1: -1+2 = 1 (op1: +2, op3: -1)
  index 2: +2+3 = 5 (op1: +2, op2: +3)
  index 3: +2+3 = 5 (op1: +2, op2: +3)
  index 4: +3 = 3 (op2: +3, op1's -2 cancels) ... 
  Actually: prefix sum: -1, -1+2=1, 1+4=5, 5+0=5, 5-2=3. Correct.
```

### Template

```java
public int[] rangeAddition(int length, int[][] updates) {
    int[] diff = new int[length];

    for (int[] update : updates) {
        int l = update[0], r = update[1], val = update[2];
        diff[l] += val;
        if (r + 1 < length) diff[r + 1] -= val;
    }

    // Convert difference array to result via prefix sum
    for (int i = 1; i < length; i++) {
        diff[i] += diff[i - 1];
    }
    return diff;
}
```

### Complexity
- O(n + q) where q = number of updates
- Without difference array: O(n * q)

---

## Pattern 8: Count Number of Nice Subarrays

### Signal
- Count subarrays with exactly k odd numbers
- LC 1248

### Key Insight

Transform: treat each element as 1 if odd, 0 if even.
Now it's "count subarrays with sum = k" -- exactly Pattern 2.

### Template

```java
public int numberOfSubarrays(int[] nums, int k) {
    Map<Integer, Integer> prefixCount = new HashMap<>();
    prefixCount.put(0, 1);
    int oddCount = 0, result = 0;

    for (int num : nums) {
        oddCount += (num & 1); // 1 if odd, 0 if even
        result += prefixCount.getOrDefault(oddCount - k, 0);
        prefixCount.merge(oddCount, 1, Integer::sum);
    }
    return result;
}
```

### Complexity
- O(n) time, O(n) space

---

## Pattern 9: Binary Subarrays with Sum

### Signal
- Count subarrays in binary array with sum = goal
- LC 930

### Key Insight

Identical to Pattern 2 with a binary array. Since values are 0/1, prefix sum is non-decreasing, so sliding window also works. But prefix sum + map is the universal approach.

### Template

```java
public int numSubarraysWithSum(int[] nums, int goal) {
    Map<Integer, Integer> prefixCount = new HashMap<>();
    prefixCount.put(0, 1);
    int sum = 0, count = 0;

    for (int num : nums) {
        sum += num;
        count += prefixCount.getOrDefault(sum - goal, 0);
        prefixCount.merge(sum, 1, Integer::sum);
    }
    return count;
}
```

### Alternative: atMost(goal) - atMost(goal - 1)

```java
public int numSubarraysWithSum(int[] nums, int goal) {
    return atMost(nums, goal) - atMost(nums, goal - 1);
}

private int atMost(int[] nums, int goal) {
    if (goal < 0) return 0;
    int left = 0, sum = 0, count = 0;
    for (int right = 0; right < nums.length; right++) {
        sum += nums[right];
        while (sum > goal) sum -= nums[left++];
        count += (right - left + 1);
    }
    return count;
}
```

### Complexity
- O(n) time, O(n) or O(1) space depending on approach

---

## Pattern 10: Prefix XOR

### Signal
- Range XOR queries
- Find subarray with XOR = target
- LC 1310: XOR Queries of a Subarray
- LC 1442: Count Triplets

### Key Insight

XOR is its own inverse: `a ^ a = 0`, `a ^ 0 = a`.

`xor(l, r) = prefix[r+1] ^ prefix[l]`

Same identity as prefix sum, just replace + with ^, - with ^.

### Template

```java
// Range XOR queries
public int[] xorQueries(int[] arr, int[][] queries) {
    int n = arr.length;
    int[] prefix = new int[n + 1];
    for (int i = 0; i < n; i++) {
        prefix[i + 1] = prefix[i] ^ arr[i];
    }

    int[] result = new int[queries.length];
    for (int i = 0; i < queries.length; i++) {
        result[i] = prefix[queries[i][1] + 1] ^ prefix[queries[i][0]];
    }
    return result;
}

// Count subarrays with XOR = k
public int subarrayXorEqualsK(int[] nums, int k) {
    Map<Integer, Integer> prefixCount = new HashMap<>();
    prefixCount.put(0, 1);
    int xor = 0, count = 0;

    for (int num : nums) {
        xor ^= num;
        count += prefixCount.getOrDefault(xor ^ k, 0); // xor ^ k is the "complement"
        prefixCount.merge(xor, 1, Integer::sum);
    }
    return count;
}
```

### Complexity
- O(n) build, O(1) query

---

## Pattern 11: Running Sum Applications

### Signal: Find Pivot Index (LC 724)

Left sum == right sum at some index.

```java
public int pivotIndex(int[] nums) {
    int total = 0;
    for (int n : nums) total += n;

    int leftSum = 0;
    for (int i = 0; i < nums.length; i++) {
        if (leftSum == total - leftSum - nums[i]) return i;
        leftSum += nums[i];
    }
    return -1;
}
```

### Signal: Minimum Operations to Reduce X to Zero (LC 1658)

Remove elements from left/right to sum to x. Equivalent to finding longest subarray with sum = totalSum - x.

```java
public int minOperations(int[] nums, int x) {
    int target = -x;
    for (int n : nums) target += n;
    if (target < 0) return -1;
    if (target == 0) return nums.length;

    // Find longest subarray with sum = target (sliding window since all positive)
    int left = 0, sum = 0, maxLen = -1;
    for (int right = 0; right < nums.length; right++) {
        sum += nums[right];
        while (sum > target) sum -= nums[left++];
        if (sum == target) maxLen = Math.max(maxLen, right - left + 1);
    }
    return maxLen == -1 ? -1 : nums.length - maxLen;
}
```

### Complexity
- O(n) time, O(1) space

---

## Summary Table

| # | Pattern | Core Technique | When |
|---|---------|---------------|------|
| 1 | Range Sum Query | `prefix[r+1] - prefix[l]` | Static array, multiple queries |
| 2 | Subarray Sum = K | Prefix + HashMap count | Count exact sum, has negatives |
| 3 | Sum divisible (exists) | Prefix mod + first index | Length >= 2, divisibility |
| 4 | Sum divisible (count) | Prefix mod + count map | Count all divisible subarrays |
| 5 | 2D Region Sum | Inclusion-exclusion | Matrix range queries |
| 6 | Product Except Self | Prefix * Suffix product | No division allowed |
| 7 | Difference Array | Mark endpoints, prefix sum | Batch range updates |
| 8 | Nice Subarrays | Transform + prefix count | Count based on property count |
| 9 | Binary Sum | Prefix count / atMost trick | Binary array exact sum |
| 10 | Prefix XOR | `prefix[r+1] ^ prefix[l]` | XOR range queries |
| 11 | Running Sum | Prefix as running total | Pivot, reduce from ends |

---

## Common Pitfalls

1. **Off-by-one**: Prefix array has length `n+1`. `prefix[0] = 0` represents empty prefix.
2. **Negative modulo**: In Java, `(-5) % 3 = -2`. Fix: `((sum % k) + k) % k`.
3. **Initialize map with (0, 1)**: The empty prefix (sum=0) exists once before we start.
4. **Integer overflow**: Use `long` for prefix sums when values are large.
5. **Difference array boundary**: `diff[r+1] -= val` -- check `r+1 < n` before writing.
