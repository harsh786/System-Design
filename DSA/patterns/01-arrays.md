# Array Patterns - Staff Interview Reference

---

## Pattern 1: Kadane's Algorithm

**Signal:** Find maximum (sum | product) subarray. Any "contiguous subarray" optimization problem.

**Template:**

```java
// Max Subarray Sum
public int maxSubArray(int[] nums) {
    int maxSoFar = nums[0], maxEndingHere = nums[0];
    for (int i = 1; i < nums.length; i++) {
        maxEndingHere = Math.max(nums[i], maxEndingHere + nums[i]);
        maxSoFar = Math.max(maxSoFar, maxEndingHere);
    }
    return maxSoFar;
}

// Max Product Subarray (track both min and max due to negative flips)
public int maxProduct(int[] nums) {
    int max = nums[0], curMax = nums[0], curMin = nums[0];
    for (int i = 1; i < nums.length; i++) {
        int tmp = curMax;
        curMax = Math.max(nums[i], Math.max(curMax * nums[i], curMin * nums[i]));
        curMin = Math.min(nums[i], Math.min(tmp * nums[i], curMin * nums[i]));
        max = Math.max(max, curMax);
    }
    return max;
}
```

**Visualization:**

```
Array: [-2, 1, -3, 4, -1, 2, 1, -5, 4]

maxEndingHere:  -2  1  -2  4   3  5  6   1  5
maxSoFar:       -2  1   1  4   4  5  6   6  6
                              ───────────
                              max subarray [4,-1,2,1] = 6
```

**Variants:**
- LC 53: Maximum Subarray
- LC 152: Maximum Product Subarray
- LC 918: Maximum Sum Circular Subarray (Kadane on total - minSubarray)
- Max subarray with at most K elements (sliding window hybrid)

**Complexity:** O(n) time, O(1) space

---

## Pattern 2: Prefix Sum + HashMap

**Signal:** "Subarray with sum = K", "divisible by K", "equal number of 0s and 1s". Anytime you need count/length of subarrays satisfying an aggregate condition.

**Template:**

```java
// Subarray Sum Equals K (count)
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

// Subarray Divisible by K
public int subarraysDivByK(int[] nums, int k) {
    Map<Integer, Integer> remainderCount = new HashMap<>();
    remainderCount.put(0, 1);
    int sum = 0, count = 0;
    for (int num : nums) {
        sum += num;
        int rem = ((sum % k) + k) % k; // handle negative modulo
        count += remainderCount.getOrDefault(rem, 0);
        remainderCount.merge(rem, 1, Integer::sum);
    }
    return count;
}

// Contiguous Array (0s and 1s) - treat 0 as -1, find sum=0 subarray
public int findMaxLength(int[] nums) {
    Map<Integer, Integer> firstIndex = new HashMap<>();
    firstIndex.put(0, -1);
    int sum = 0, maxLen = 0;
    for (int i = 0; i < nums.length; i++) {
        sum += (nums[i] == 0) ? -1 : 1;
        if (firstIndex.containsKey(sum))
            maxLen = Math.max(maxLen, i - firstIndex.get(sum));
        else
            firstIndex.put(sum, i);
    }
    return maxLen;
}
```

**Visualization:**

```
Problem: subarraySum(nums, k=7)

Array:       [3,  4,  7,  2, -3,  1,  4,  2]
Prefix Sum:   3   7  14  16  13  14  18  20

HashMap stores prefix → count
At index 2: prefix=14, check 14-7=7 exists? YES (index 1) → count++
At index 5: prefix=14, check 14-7=7 exists? YES → count++

Key insight: prefix[j] - prefix[i] = sum(i+1..j)
             If prefix[j] - k exists in map → subarray found

          prefix[i]          prefix[j]
    ├──────────┤├─────────────────┤
    0          i               j
               ├──── sum = k ────┤
```

**Variants:**
- LC 560: Subarray Sum Equals K
- LC 974: Subarray Sums Divisible by K
- LC 525: Contiguous Array
- LC 523: Continuous Subarray Sum (sum multiple of k)
- LC 930: Binary Subarrays With Sum
- LC 1248: Count Number of Nice Subarrays

**Complexity:** O(n) time, O(n) space

---

## Pattern 3: Dutch National Flag (3-Way Partition)

**Signal:** Partition array into 3 groups in-place. Sort an array with only 2-3 distinct values. "Sort Colors."

**Template:**

```java
// Sort Colors (0, 1, 2)
public void sortColors(int[] nums) {
    int lo = 0, mid = 0, hi = nums.length - 1;
    while (mid <= hi) {
        if (nums[mid] == 0) {
            swap(nums, lo++, mid++);
        } else if (nums[mid] == 1) {
            mid++;
        } else { // nums[mid] == 2
            swap(nums, mid, hi--);
            // don't advance mid — swapped element needs inspection
        }
    }
}

private void swap(int[] a, int i, int j) {
    int tmp = a[i]; a[i] = a[j]; a[j] = tmp;
}
```

**Visualization:**

```
Invariant maintained throughout:

[  0s   |   1s   | unexplored |   2s   ]
 0      lo      mid          hi      n-1

Step-by-step on [2, 0, 2, 1, 1, 0]:
lo=0 mid=0 hi=5: nums[0]=2 → swap(0,5) → [0,0,2,1,1,2] hi=4
lo=0 mid=0 hi=4: nums[0]=0 → lo=1 mid=1
lo=1 mid=1 hi=4: nums[1]=0 → lo=2 mid=2
lo=2 mid=2 hi=4: nums[2]=2 → swap(2,4) → [0,0,1,1,2,2] hi=3
lo=2 mid=2 hi=3: nums[2]=1 → mid=3
lo=2 mid=3 hi=3: nums[3]=1 → mid=4
mid > hi → DONE: [0,0,1,1,2,2]
```

**Variants:**
- LC 75: Sort Colors
- LC 324: Wiggle Sort II (3-way partition around median)
- Partition around pivot (quickselect subroutine)
- Move negatives left, positives right, zeros middle

**Complexity:** O(n) time, O(1) space, single pass

---

## Pattern 4: Boyer-Moore Voting Algorithm

**Signal:** Find element appearing > n/2 times (majority) or > n/3 times. "Guaranteed to exist" majority element.

**Template:**

```java
// Majority Element (> n/2)
public int majorityElement(int[] nums) {
    int candidate = 0, count = 0;
    for (int num : nums) {
        if (count == 0) candidate = num;
        count += (num == candidate) ? 1 : -1;
    }
    return candidate; // guaranteed to exist
}

// Elements appearing > n/3 (at most 2 such elements)
public List<Integer> majorityElementN3(int[] nums) {
    int c1 = 0, c2 = 0, cnt1 = 0, cnt2 = 0;
    for (int num : nums) {
        if (num == c1) cnt1++;
        else if (num == c2) cnt2++;
        else if (cnt1 == 0) { c1 = num; cnt1 = 1; }
        else if (cnt2 == 0) { c2 = num; cnt2 = 1; }
        else { cnt1--; cnt2--; }
    }
    // Verify (required if not guaranteed)
    List<Integer> res = new ArrayList<>();
    cnt1 = 0; cnt2 = 0;
    for (int num : nums) {
        if (num == c1) cnt1++;
        else if (num == c2) cnt2++;
    }
    if (cnt1 > nums.length / 3) res.add(c1);
    if (cnt2 > nums.length / 3) res.add(c2);
    return res;
}
```

**Visualization:**

```
Array: [2, 2, 1, 1, 1, 2, 2]

candidate: 2  2  2  1  1  1  2
count:     1  2  1  0  1  2  1  → but count=0 triggers reset...

Actually:
i=0: count=0 → candidate=2, count=1
i=1: 2==2 → count=2
i=2: 1!=2 → count=1
i=3: 1!=2 → count=0
i=4: count=0 → candidate=1, count=1
i=5: 2!=1 → count=0
i=6: count=0 → candidate=2, count=1

Result: 2 (correct — appears 4/7 > n/2)

Intuition: Majority element survives all "cancellations"
           because it has more copies than all others combined.
```

**Variants:**
- LC 169: Majority Element
- LC 229: Majority Element II (> n/3)
- Generalization: > n/k requires k-1 candidates

**Complexity:** O(n) time, O(1) space

---

## Pattern 5: Cyclic Sort / Index as Hash

**Signal:** Array contains numbers in range [1, n] or [0, n]. Find missing/duplicate without extra space. "First missing positive."

**Template:**

```java
// First Missing Positive
public int firstMissingPositive(int[] nums) {
    int n = nums.length;
    // Place each number at its "correct" index: num → index num-1
    for (int i = 0; i < n; i++) {
        while (nums[i] > 0 && nums[i] <= n && nums[nums[i] - 1] != nums[i]) {
            swap(nums, i, nums[i] - 1);
        }
    }
    // First index where nums[i] != i+1 is the answer
    for (int i = 0; i < n; i++) {
        if (nums[i] != i + 1) return i + 1;
    }
    return n + 1;
}

// Find All Duplicates (numbers 1..n, some appear twice)
public List<Integer> findDuplicates(int[] nums) {
    List<Integer> res = new ArrayList<>();
    for (int i = 0; i < nums.length; i++) {
        int idx = Math.abs(nums[i]) - 1;
        if (nums[idx] < 0) res.add(idx + 1); // seen before
        else nums[idx] = -nums[idx];          // mark visited
    }
    return res;
}
```

**Visualization:**

```
First Missing Positive on [3, 4, -1, 1]:

Goal: place value v at index v-1

i=0: nums[0]=3 → swap to index 2 → [-1, 4, 3, 1]
     nums[0]=-1 → skip (out of range)
i=1: nums[1]=4 → swap to index 3 → [-1, 1, 3, 4]
     nums[1]=1 → swap to index 0 → [1, -1, 3, 4]
     nums[1]=-1 → skip
i=2: nums[2]=3 → index 2, already correct
i=3: nums[3]=4 → index 3, already correct

Final: [1, -1, 3, 4]
        ✓   ✗  ✓  ✓
            ↑
        index 1 → missing value = 2
```

**Variants:**
- LC 41: First Missing Positive
- LC 442: Find All Duplicates in an Array
- LC 448: Find All Numbers Disappeared in an Array
- LC 268: Missing Number
- LC 287: Find the Duplicate Number (Floyd's cycle)

**Complexity:** O(n) time, O(1) space (each element swapped at most once)

---

## Pattern 6: Interval Merge/Overlap

**Signal:** Problems involving intervals, ranges, schedules. "Merge overlapping", "insert interval", "minimum meeting rooms."

**Template:**

```java
// Merge Intervals
public int[][] merge(int[][] intervals) {
    Arrays.sort(intervals, (a, b) -> a[0] - b[0]);
    List<int[]> merged = new ArrayList<>();
    for (int[] iv : intervals) {
        if (merged.isEmpty() || merged.get(merged.size() - 1)[1] < iv[0]) {
            merged.add(iv);
        } else {
            merged.get(merged.size() - 1)[1] =
                Math.max(merged.get(merged.size() - 1)[1], iv[1]);
        }
    }
    return merged.toArray(new int[0][]);
}

// Insert Interval (already sorted, no need to sort)
public int[][] insert(int[][] intervals, int[] newInterval) {
    List<int[]> res = new ArrayList<>();
    int i = 0, n = intervals.length;
    // Add all before
    while (i < n && intervals[i][1] < newInterval[0])
        res.add(intervals[i++]);
    // Merge overlapping
    while (i < n && intervals[i][0] <= newInterval[1]) {
        newInterval[0] = Math.min(newInterval[0], intervals[i][0]);
        newInterval[1] = Math.max(newInterval[1], intervals[i][1]);
        i++;
    }
    res.add(newInterval);
    // Add all after
    while (i < n) res.add(intervals[i++]);
    return res.toArray(new int[0][]);
}
```

**Visualization:**

```
Merge Intervals: [[1,3],[2,6],[8,10],[15,18]]

Sorted by start:
[1,3]  [2,6]  [8,10]  [15,18]

Timeline:
1───3
  2─────6
              8──10
                        15──18

Merged:
1───────6     8──10     15──18

Result: [[1,6],[8,10],[15,18]]

Overlap condition: prev.end >= curr.start
```

**Variants:**
- LC 56: Merge Intervals
- LC 57: Insert Interval
- LC 435: Non-overlapping Intervals (greedy - sort by end)
- LC 252/253: Meeting Rooms I/II
- LC 986: Interval List Intersections
- LC 1288: Remove Covered Intervals

**Complexity:** O(n log n) time (sort), O(n) space for output

---

## Pattern 7: Two-Pass Left-Right

**Signal:** Answer at each index depends on information from BOTH left and right sides. "Product except self", "trapping rain water", "candy distribution."

**Template:**

```java
// Product of Array Except Self
public int[] productExceptSelf(int[] nums) {
    int n = nums.length;
    int[] res = new int[n];
    // Left pass: res[i] = product of all elements to the left
    res[0] = 1;
    for (int i = 1; i < n; i++)
        res[i] = res[i - 1] * nums[i - 1];
    // Right pass: multiply by product of all elements to the right
    int right = 1;
    for (int i = n - 1; i >= 0; i--) {
        res[i] *= right;
        right *= nums[i];
    }
    return res;
}

// Trapping Rain Water
public int trap(int[] height) {
    int n = height.length;
    int[] leftMax = new int[n], rightMax = new int[n];
    leftMax[0] = height[0];
    for (int i = 1; i < n; i++)
        leftMax[i] = Math.max(leftMax[i - 1], height[i]);
    rightMax[n - 1] = height[n - 1];
    for (int i = n - 2; i >= 0; i--)
        rightMax[i] = Math.max(rightMax[i + 1], height[i]);
    int water = 0;
    for (int i = 0; i < n; i++)
        water += Math.min(leftMax[i], rightMax[i]) - height[i];
    return water;
}

// Candy (each child gets at least 1; higher rating → more than neighbor)
public int candy(int[] ratings) {
    int n = ratings.length;
    int[] candies = new int[n];
    Arrays.fill(candies, 1);
    for (int i = 1; i < n; i++)          // left to right
        if (ratings[i] > ratings[i - 1])
            candies[i] = candies[i - 1] + 1;
    for (int i = n - 2; i >= 0; i--)     // right to left
        if (ratings[i] > ratings[i + 1])
            candies[i] = Math.max(candies[i], candies[i + 1] + 1);
    return Arrays.stream(candies).sum();
}
```

**Visualization:**

```
Product Except Self: [1, 2, 3, 4]

Left products:   [1,  1,  2,  6 ]  ← product of everything to the left
Right products:  [24, 12, 4,  1 ]  ← product of everything to the right
Result:          [24, 12, 8,  6 ]  ← left[i] * right[i]

─────────────────────────────────────────

Trapping Rain Water: [0,1,0,2,1,0,1,3,2,1,2,1]

      █
  █   ██ █
  █ █ ████ █
──────────────
leftMax:  0 1 1 2 2 2 2 3 3 3 3 3
rightMax: 3 3 3 3 3 3 3 3 2 2 2 1
water[i]: min(L,R)-h[i]
          0 0 1 0 1 2 1 0 0 1 0 0  → total = 6
```

**Variants:**
- LC 238: Product of Array Except Self
- LC 42: Trapping Rain Water (also solvable with two pointers / stack)
- LC 135: Candy
- LC 845: Longest Mountain in Array
- LC 821: Shortest Distance to a Character

**Complexity:** O(n) time, O(1) extra space (Product Except Self), O(n) for others

---

## Pattern 8: Read/Write Pointer (In-Place Compaction)

**Signal:** Remove elements in-place, compact array. "Remove duplicates from sorted array", "move zeroes." Maintain relative order.

**Template:**

```java
// Remove Duplicates from Sorted Array
public int removeDuplicates(int[] nums) {
    if (nums.length == 0) return 0;
    int write = 1; // write pointer
    for (int read = 1; read < nums.length; read++) {
        if (nums[read] != nums[read - 1]) {
            nums[write++] = nums[read];
        }
    }
    return write;
}

// Remove Duplicates II (allow at most 2)
public int removeDuplicatesII(int[] nums) {
    int write = 0;
    for (int num : nums) {
        if (write < 2 || num != nums[write - 2]) {
            nums[write++] = num;
        }
    }
    return write;
}

// Move Zeroes
public void moveZeroes(int[] nums) {
    int write = 0;
    for (int read = 0; read < nums.length; read++) {
        if (nums[read] != 0) {
            nums[write++] = nums[read];
        }
    }
    while (write < nums.length) nums[write++] = 0;
}
```

**Visualization:**

```
Remove Duplicates from [1, 1, 2, 2, 3]:

read:   ↓
write:  ↓
        [1, 1, 2, 2, 3]

Step-by-step:
read=1: nums[1]=1 == nums[0]=1 → skip
read=2: nums[2]=2 != nums[1]=1 → write! nums[1]=2, write=2
read=3: nums[3]=2 == nums[2]=2 → skip
read=4: nums[4]=3 != nums[3]=2 → write! nums[2]=3, write=3

Result: [1, 2, 3, _, _]  return write=3
         w        r
         ─────────
         valid portion

Invariant: nums[0..write-1] contains the valid output
```

**Variants:**
- LC 26: Remove Duplicates from Sorted Array
- LC 80: Remove Duplicates from Sorted Array II
- LC 283: Move Zeroes
- LC 27: Remove Element
- LC 905: Sort Array By Parity

**Complexity:** O(n) time, O(1) space

---

## Pattern 9: Rotate Array (Triple Reverse Trick)

**Signal:** Rotate array by k positions. Any cyclic shift in-place.

**Template:**

```java
public void rotate(int[] nums, int k) {
    int n = nums.length;
    k %= n; // handle k > n
    reverse(nums, 0, n - 1);     // reverse entire array
    reverse(nums, 0, k - 1);     // reverse first k
    reverse(nums, k, n - 1);     // reverse remaining
}

private void reverse(int[] nums, int l, int r) {
    while (l < r) {
        int tmp = nums[l];
        nums[l++] = nums[r];
        nums[r--] = tmp;
    }
}
```

**Visualization:**

```
Rotate [1, 2, 3, 4, 5, 6, 7] by k=3:

Step 1 - Reverse all:       [7, 6, 5, 4, 3, 2, 1]
Step 2 - Reverse [0..k-1]:  [5, 6, 7, 4, 3, 2, 1]
Step 3 - Reverse [k..n-1]:  [5, 6, 7, 1, 2, 3, 4]  ✓

Why it works:
Original:  [A | B]  where A = [1..4], B = [5..7]
Want:      [B | A]

rev(AB)  = rev(B) rev(A)     → [7,6,5 | 4,3,2,1]
rev(rev(B)) rev(rev(A)) = B A → [5,6,7 | 1,2,3,4]
```

**Variants:**
- LC 189: Rotate Array
- LC 61: Rotate List (linked list variant)
- LC 796: Rotate String (concatenation trick: s+s contains all rotations)
- Rotate matrix 90 degrees (transpose + reverse rows)

**Complexity:** O(n) time, O(1) space

---

## Decision Flowchart

```
                    ┌─────────────────────────┐
                    │   Array Problem Arrived  │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │ Numbers in range [1..n]? │
                    └──┬─────────────────┬────┘
                   YES │                 │ NO
                       ▼                 ▼
              ┌────────────────┐  ┌──────────────────┐
              │ Cyclic Sort /  │  │ Contiguous        │
              │ Index-as-Hash  │  │ subarray problem? │
              │ (Pattern 5)    │  └──┬───────────┬───┘
              └────────────────┘  YES│           │NO
                                     ▼           ▼
                        ┌────────────────┐  ┌──────────────────┐
                        │ Optimize sum/  │  │ Intervals/ranges?│
                        │ product?       │  └──┬───────────┬───┘
                        └──┬─────────┬───┘  YES│           │NO
                       YES │         │ NO      ▼           ▼
                           ▼         ▼    ┌──────────┐ ┌────────────────┐
                  ┌──────────┐  ┌───────┐ │ Interval │ │ In-place       │
                  │ Kadane's │  │Prefix │ │ Merge    │ │ modification?  │
                  │(Pattern 1)│ │Sum+Map│ │(Pattern 6)│ └──┬─────────┬──┘
                  └──────────┘  │(Pat 2)│ └──────────┘ YES│         │NO
                                └───────┘                  ▼         ▼
                                              ┌────────────────┐ ┌──────────┐
                                              │ Remove/compact?│ │Need info │
                                              └──┬─────────┬───┘ │from both │
                                             YES │         │NO   │ sides?   │
                                                 ▼         ▼     └──┬───┬───┘
                                        ┌──────────┐ ┌────────┐ YES│   │NO
                                        │Read/Write│ │Rotate? │    ▼   ▼
                                        │(Pattern 8)│ └───┬────┘ ┌──────┐ ┌─────────┐
                                        └──────────┘     ▼      │L-R   │ │Majority/│
                                                   ┌──────────┐ │Pass  │ │Partition?│
                                                   │Triple Rev│ │(Pat 7)│ └──┬───┬──┘
                                                   │(Pattern 9)│ └──────┘ MAJ│   │PART
                                                   └──────────┘              ▼   ▼
                                                                      ┌─────┐ ┌─────┐
                                                                      │Boyer│ │Dutch│
                                                                      │Moore│ │Flag │
                                                                      │(P 4)│ │(P 3)│
                                                                      └─────┘ └─────┘
```

### Quick Reference Table

| Signal | Pattern |
|--------|---------|
| Max/min contiguous subarray sum/product | Kadane's (#1) |
| Count/length subarrays with sum=K, divisible | Prefix Sum + HashMap (#2) |
| Partition into exactly 3 groups in-place | Dutch National Flag (#3) |
| Find element appearing > n/k times | Boyer-Moore Voting (#4) |
| Numbers in [1..n], find missing/duplicate | Cyclic Sort (#5) |
| Merge/insert/count overlapping intervals | Interval Merge (#6) |
| Each position needs left AND right context | Two-Pass L-R (#7) |
| Remove/compact elements in-place, maintain order | Read/Write Pointer (#8) |
| Cyclic shift array by k | Triple Reverse (#9) |

---

*Prepared for Staff Architect interview preparation. Each pattern is O(n) or O(n log n) and uses O(1) auxiliary space where possible.*
