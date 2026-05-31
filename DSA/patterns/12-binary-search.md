# Binary Search Patterns

## Mental Model: The Predicate Boundary

Every binary search problem reduces to finding a **boundary** where a predicate flips from FALSE to TRUE (or vice versa).

```
Index:     0   1   2   3   4   5   6   7   8
Predicate: F   F   F   F   T   T   T   T   T
                         ^   ^
                         |   |
                    last FALSE  first TRUE
                    (upper bound) (lower bound)
```

**Key Insight**: You never "search for a value." You search for a boundary in a monotonic predicate. Once you internalize this, every variant becomes the same algorithm with a different predicate.

---

## Template Comparison Table

| Template | Loop Condition | Update | Terminates With | Best For |
|----------|---------------|--------|-----------------|----------|
| **A** `lo <= hi` | `lo <= hi` | `lo = mid+1` / `hi = mid-1` | `lo > hi` (crossed) | Exact match, answer space |
| **B** `lo < hi` | `lo < hi` | `lo = mid+1` / `hi = mid` | `lo == hi` (converged) | First TRUE / lower bound |
| **C** `lo + 1 < hi` | `lo + 1 < hi` | `lo = mid` / `hi = mid` | `lo + 1 == hi` (adjacent) | When you need both neighbors |

### Template A: Exact Match / Answer Space
```java
int lo = 0, hi = n - 1;
while (lo <= hi) {
    int mid = lo + (hi - lo) / 2;
    if (arr[mid] == target) return mid;
    else if (arr[mid] < target) lo = mid + 1;
    else hi = mid - 1;
}
return -1; // not found
```

### Template B: Find First TRUE (Lower Bound) -- THE UNIVERSAL TEMPLATE
```java
int lo = 0, hi = n; // hi = n (one past end, the "always TRUE" sentinel)
while (lo < hi) {
    int mid = lo + (hi - lo) / 2;
    if (predicate(mid)) hi = mid;   // mid could be answer, keep it
    else lo = mid + 1;              // mid is FALSE, discard it
}
return lo; // first index where predicate is TRUE
```

### Template C: Neighbor-Aware
```java
int lo = 0, hi = n - 1;
while (lo + 1 < hi) {
    int mid = lo + (hi - lo) / 2;
    if (condition(mid)) hi = mid;
    else lo = mid;
}
// Check both lo and hi
```

---

## Decision Flowchart

```
START: Is the search space monotonic w.r.t. some predicate?
  |
  YES --> Do you need the FIRST position where predicate holds?
  |         |
  |         YES --> Template B (lo < hi), hi = mid
  |         |
  |         NO --> Do you need the LAST position?
  |                  |
  |                  YES --> Flip predicate, use Template B
  |                          OR use Template B with lo = mid + 1, return lo - 1
  |                  |
  |                  NO --> Exact match? --> Template A (lo <= hi)
  |
  NO --> Can you DEFINE a monotonic predicate over the answer space?
           |
           YES --> Binary Search on Answer (Template A or B on answer space)
           |
           NO --> Not a binary search problem.
```

---

## Pattern 1: Classic Search (Exact Element)

### Signal
- Sorted array, find index of target.

### Template
```java
public int search(int[] nums, int target) {
    int lo = 0, hi = nums.length - 1;
    while (lo <= hi) {
        int mid = lo + (hi - lo) / 2;
        if (nums[mid] == target) return mid;
        else if (nums[mid] < target) lo = mid + 1;
        else hi = mid - 1;
    }
    return -1;
}
```

### Complexity
- Time: O(log n) | Space: O(1)

---

## Pattern 2: First TRUE / Lower Bound

### Signal
- "Find the first element >= target"
- "Minimum index satisfying condition"
- Any problem asking for leftmost boundary.

### Visualization
```
arr:       [1, 3, 5, 5, 5, 7, 9]
target=5
predicate: arr[i] >= 5
           F  F  T  T  T  T  T
                 ^
                 answer = index 2
```

### Template
```java
// Returns first index where arr[i] >= target (insertion point)
public int lowerBound(int[] arr, int target) {
    int lo = 0, hi = arr.length;
    while (lo < hi) {
        int mid = lo + (hi - lo) / 2;
        if (arr[mid] >= target) hi = mid;
        else lo = mid + 1;
    }
    return lo;
}
```

### Complexity
- Time: O(log n) | Space: O(1)

---

## Pattern 3: Last TRUE / Upper Bound

### Signal
- "Find the last element <= target"
- "Maximum index satisfying condition"
- Rightmost boundary.

### Visualization
```
arr:       [1, 3, 5, 5, 5, 7, 9]
target=5
predicate: arr[i] <= 5
           T  T  T  T  T  F  F
                       ^
                       answer = index 4
```

### Template
```java
// Returns last index where arr[i] <= target
public int upperBound(int[] arr, int target) {
    int lo = 0, hi = arr.length;
    while (lo < hi) {
        int mid = lo + (hi - lo) / 2;
        if (arr[mid] <= target) lo = mid + 1;  // mid is valid, but maybe more to the right
        else hi = mid;
    }
    return lo - 1; // lo is first index where arr[i] > target, so lo-1 is last <=
}
```

**Alternatively (flip predicate):** Find first index where `arr[i] > target`, then subtract 1.

### Complexity
- Time: O(log n) | Space: O(1)

---

## Pattern 4: Binary Search on Answer

### Signal
- "Minimize the maximum" / "Maximize the minimum"
- The answer is a numeric value in a range, and you can CHECK feasibility in O(n) or O(n log n).
- Keywords: "minimum time", "maximum distance", "at most k splits".

### Core Idea
```
Answer space:  [minPossible ... maxPossible]
Predicate:     canAchieve(mid) -> boolean (monotonic!)

For MINIMIZE: find first TRUE  (Template B, hi = mid)
For MAXIMIZE: find last TRUE   (Template B, lo = mid + 1, return lo - 1)
```

### Variant A: Koko Eating Bananas (LC 875)
```java
// Minimize eating speed k such that Koko finishes within h hours
public int minEatingSpeed(int[] piles, int h) {
    int lo = 1, hi = max(piles);
    while (lo < hi) {
        int mid = lo + (hi - lo) / 2;
        if (canFinish(piles, mid, h)) hi = mid;  // try slower
        else lo = mid + 1;                        // too slow
    }
    return lo;
}

private boolean canFinish(int[] piles, int speed, int h) {
    int hours = 0;
    for (int p : piles) hours += (p + speed - 1) / speed; // ceil division
    return hours <= h;
}
```

### Variant B: Split Array Largest Sum (LC 410)
```java
// Minimize the largest sum when splitting into k subarrays
public int splitArray(int[] nums, int k) {
    int lo = max(nums), hi = sum(nums);
    while (lo < hi) {
        int mid = lo + (hi - lo) / 2;
        if (canSplit(nums, mid, k)) hi = mid;
        else lo = mid + 1;
    }
    return lo;
}

private boolean canSplit(int[] nums, int maxSum, int k) {
    int splits = 1, curSum = 0;
    for (int n : nums) {
        if (curSum + n > maxSum) { splits++; curSum = n; }
        else curSum += n;
    }
    return splits <= k;
}
```

### Variant C: Capacity to Ship Packages (LC 1011)
```java
// Minimize ship capacity to finish in 'days' days
public int shipWithinDays(int[] weights, int days) {
    int lo = max(weights), hi = sum(weights);
    while (lo < hi) {
        int mid = lo + (hi - lo) / 2;
        if (canShip(weights, mid, days)) hi = mid;
        else lo = mid + 1;
    }
    return lo;
}

private boolean canShip(int[] weights, int cap, int days) {
    int d = 1, load = 0;
    for (int w : weights) {
        if (load + w > cap) { d++; load = w; }
        else load += w;
    }
    return d <= days;
}
```

### Variant D: Magnetic Force Between Two Balls (LC 1552)
```java
// MAXIMIZE minimum distance (find last TRUE)
public int maxDistance(int[] position, int m) {
    Arrays.sort(position);
    int lo = 1, hi = position[position.length - 1] - position[0];
    while (lo < hi) {
        int mid = lo + (hi - lo + 1) / 2; // upper mid to avoid infinite loop
        if (canPlace(position, mid, m)) lo = mid;   // feasible, try larger
        else hi = mid - 1;
    }
    return lo;
}

private boolean canPlace(int[] pos, int minDist, int m) {
    int count = 1, last = pos[0];
    for (int i = 1; i < pos.length; i++) {
        if (pos[i] - last >= minDist) { count++; last = pos[i]; }
    }
    return count >= m;
}
```

**Note on MAXIMIZE pattern:** When searching for last TRUE with `lo = mid`, you MUST use upper-mid: `mid = lo + (hi - lo + 1) / 2` to avoid infinite loop when `hi - lo == 1`.

### Complexity
- Time: O(n * log(answer_range)) | Space: O(1)

---

## Pattern 5: Search in Rotated Sorted Array (LC 33)

### Signal
- Sorted array rotated at unknown pivot. Find target.

### Key Insight
At any `mid`, one half is always sorted. Determine which half is sorted, then check if target lies in that sorted half.

### Visualization
```
[4, 5, 6, 7, 0, 1, 2]
         ^pivot
 sorted half    sorted half

mid=3 (value 7): left half [4,5,6,7] is sorted
  - target in [4,7]? search left
  - else search right
```

### Template
```java
public int search(int[] nums, int target) {
    int lo = 0, hi = nums.length - 1;
    while (lo <= hi) {
        int mid = lo + (hi - lo) / 2;
        if (nums[mid] == target) return mid;

        // Left half is sorted
        if (nums[lo] <= nums[mid]) {
            if (nums[lo] <= target && target < nums[mid])
                hi = mid - 1;
            else
                lo = mid + 1;
        }
        // Right half is sorted
        else {
            if (nums[mid] < target && target <= nums[hi])
                lo = mid + 1;
            else
                hi = mid - 1;
        }
    }
    return -1;
}
```

### With Duplicates (LC 81)
Add: `if (nums[lo] == nums[mid] && nums[mid] == nums[hi]) { lo++; hi--; continue; }`
Worst case degrades to O(n).

### Complexity
- Time: O(log n) [O(n) with duplicates worst case] | Space: O(1)

---

## Pattern 6: Find Minimum in Rotated Array (LC 153)

### Signal
- Rotated sorted array, find minimum element.

### Key Insight
Compare `mid` with `hi`. If `nums[mid] > nums[hi]`, min is in right half. Otherwise, min is in left half (including mid).

### Template
```java
public int findMin(int[] nums) {
    int lo = 0, hi = nums.length - 1;
    while (lo < hi) {
        int mid = lo + (hi - lo) / 2;
        if (nums[mid] > nums[hi])
            lo = mid + 1;   // min is strictly to the right
        else
            hi = mid;       // mid could be the min
    }
    return nums[lo];
}
```

### With Duplicates (LC 154)
```java
public int findMin(int[] nums) {
    int lo = 0, hi = nums.length - 1;
    while (lo < hi) {
        int mid = lo + (hi - lo) / 2;
        if (nums[mid] > nums[hi]) lo = mid + 1;
        else if (nums[mid] < nums[hi]) hi = mid;
        else hi--;  // can't determine, shrink safely
    }
    return nums[lo];
}
```

### Complexity
- Time: O(log n) [O(n) with duplicates] | Space: O(1)

---

## Pattern 7: Peak Element Finding (LC 162)

### Signal
- Find ANY peak (element greater than its neighbors).
- Array has no duplicates, `nums[-1] = nums[n] = -inf`.

### Key Insight
If `nums[mid] < nums[mid+1]`, a peak MUST exist to the right (by the uphill guarantee). This creates a monotonic predicate.

### Visualization
```
[1, 3, 5, 4, 2]
         ^peak

mid=2: nums[2]=5 > nums[3]=4 → peak is at mid or left → hi = mid
mid=1: nums[1]=3 < nums[2]=5 → peak is to the right → lo = mid + 1
converge at index 2
```

### Template
```java
public int findPeakElement(int[] nums) {
    int lo = 0, hi = nums.length - 1;
    while (lo < hi) {
        int mid = lo + (hi - lo) / 2;
        if (nums[mid] < nums[mid + 1])
            lo = mid + 1;  // peak is to the right
        else
            hi = mid;      // mid could be peak
    }
    return lo;
}
```

### Complexity
- Time: O(log n) | Space: O(1)

---

## Pattern 8: Median of Two Sorted Arrays (LC 4)

### Signal
- Two sorted arrays, find median in O(log(min(m,n))).

### Key Insight
Binary search on the **partition position** of the smaller array. A valid partition splits both arrays such that all left elements <= all right elements.

### Visualization
```
A: [1, 3, | 8, 9]     partitionA = 2
B: [2, | 4, 5, 6, 7]  partitionB = 1
     left     |    right
   [1,2,3]   |  [4,5,6,7,8,9]

Valid if: maxLeftA <= minRightB AND maxLeftB <= minRightA
          3 <= 4  ✓              2 <= 8  ✓
```

### Template
```java
public double findMedianSortedArrays(int[] nums1, int[] nums2) {
    // Ensure nums1 is shorter
    if (nums1.length > nums2.length) return findMedianSortedArrays(nums2, nums1);

    int m = nums1.length, n = nums2.length;
    int lo = 0, hi = m;
    int halfLen = (m + n + 1) / 2;

    while (lo <= hi) {
        int i = lo + (hi - lo) / 2;  // partition in nums1
        int j = halfLen - i;          // partition in nums2

        int maxLeftA  = (i == 0) ? Integer.MIN_VALUE : nums1[i - 1];
        int minRightA = (i == m) ? Integer.MAX_VALUE : nums1[i];
        int maxLeftB  = (j == 0) ? Integer.MIN_VALUE : nums2[j - 1];
        int minRightB = (j == n) ? Integer.MAX_VALUE : nums2[j];

        if (maxLeftA <= minRightB && maxLeftB <= minRightA) {
            // Valid partition found
            if ((m + n) % 2 == 0)
                return (Math.max(maxLeftA, maxLeftB) + Math.min(minRightA, minRightB)) / 2.0;
            else
                return Math.max(maxLeftA, maxLeftB);
        } else if (maxLeftA > minRightB) {
            hi = i - 1;  // too many from A on left
        } else {
            lo = i + 1;  // too few from A on left
        }
    }
    throw new IllegalArgumentException();
}
```

### Complexity
- Time: O(log(min(m, n))) | Space: O(1)

---

## Pattern 9: Search a 2D Matrix (LC 74)

### Signal
- m x n matrix where each row is sorted and first element of each row > last element of previous row.
- Treat as a flattened sorted 1D array.

### Template
```java
public boolean searchMatrix(int[][] matrix, int target) {
    int m = matrix.length, n = matrix[0].length;
    int lo = 0, hi = m * n - 1;
    while (lo <= hi) {
        int mid = lo + (hi - lo) / 2;
        int val = matrix[mid / n][mid % n];  // convert 1D index to 2D
        if (val == target) return true;
        else if (val < target) lo = mid + 1;
        else hi = mid - 1;
    }
    return false;
}
```

### For LC 240 (rows sorted, cols sorted, but not globally sorted):
Use staircase search from top-right: O(m + n), not binary search.

### Complexity
- Time: O(log(m*n)) | Space: O(1)

---

## Pattern 10: Find First and Last Position (LC 34)

### Signal
- Sorted array with duplicates, find range `[first, last]` of target.

### Key Insight
Run lower bound twice: once for `target`, once for `target + 1`.

### Template
```java
public int[] searchRange(int[] nums, int target) {
    int first = lowerBound(nums, target);
    if (first == nums.length || nums[first] != target)
        return new int[]{-1, -1};
    int last = lowerBound(nums, target + 1) - 1;
    return new int[]{first, last};
}

private int lowerBound(int[] nums, int target) {
    int lo = 0, hi = nums.length;
    while (lo < hi) {
        int mid = lo + (hi - lo) / 2;
        if (nums[mid] >= target) hi = mid;
        else lo = mid + 1;
    }
    return lo;
}
```

### Complexity
- Time: O(log n) | Space: O(1)

---

## Common Pitfalls

### 1. Infinite Loop
```
WRONG: lo < hi with lo = mid (when hi - lo == 1, mid == lo, loop never terminates)
FIX:   Use upper-mid: mid = lo + (hi - lo + 1) / 2  when doing lo = mid
```

### 2. Off-by-One in Search Space
```
WRONG: hi = n - 1 when answer could be n (e.g., all elements < target, insertion at end)
FIX:   hi = n for lower bound searches (the "virtual TRUE sentinel")
```

### 3. Integer Overflow in Mid Calculation
```
WRONG: mid = (lo + hi) / 2  (overflows if lo + hi > Integer.MAX_VALUE)
FIX:   mid = lo + (hi - lo) / 2
```

### 4. Wrong Half Elimination
```
WRONG: Discarding mid when it could be the answer
       e.g., hi = mid - 1 when mid might be the first TRUE
FIX:   If mid could be answer: hi = mid (keep it)
       If mid cannot be answer: lo = mid + 1 (discard it)
```

### 5. Incorrect Predicate Monotonicity
```
Verify: your predicate is FFFFFF...TTTTT (or TTTTT...FFFFF)
If it's not monotonic, binary search is inapplicable.
```

---

## Quick Reference: Which Template?

| Problem Type | Template | lo init | hi init | Return |
|---|---|---|---|---|
| Exact match | `lo <= hi` | 0 | n-1 | mid or -1 |
| First >= target | `lo < hi` | 0 | n | lo |
| Last <= target | `lo < hi` | 0 | n | lo - 1 |
| Minimize answer | `lo < hi` | min | max | lo |
| Maximize answer | `lo < hi` | min | max | lo (with upper-mid + lo=mid) |
| Peak / rotated | `lo < hi` | 0 | n-1 | lo |

---

## Summary: The One Rule

> **If you can define a monotonic boolean predicate over the search space, you can binary search.**

The only things that change between problems are:
1. What is the search space? (indices, values, answer range)
2. What is the predicate? (feasibility check, comparison)
3. Do you want first TRUE or last TRUE?
