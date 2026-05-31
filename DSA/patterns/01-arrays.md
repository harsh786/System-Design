# Arrays - Pattern Guide

> Arrays are the foundation. Most patterns here apply to other structures too.

---

## Pattern Recognition Signals

| Signal in Problem | Pattern to Apply |
|---|---|
| Max/min contiguous subarray sum | Kadane's Algorithm |
| Subarray sum = K / divisible by K | Prefix Sum + HashMap |
| Sort 3 distinct values in-place | Dutch National Flag |
| Element appearing > n/2 or > n/3 | Boyer-Moore Voting |
| Values in [1..n], find missing/dup | Cyclic Sort / Index Mapping |
| Merge/count overlapping intervals | Sort + Linear Scan |
| Rotate by K positions | Triple Reverse |
| Product except self (no division) | Two-Pass Left-Right |
| Remove/move elements in-place | Read/Write Pointer |

---

## Pattern 1: Kadane's Algorithm

**When:** Maximum (or minimum) sum contiguous subarray.

### Template
```java
int maxSum = nums[0], curSum = nums[0];
for (int i = 1; i < n; i++) {
    curSum = Math.max(nums[i], curSum + nums[i]);  // restart or extend
    maxSum = Math.max(maxSum, curSum);
}
return maxSum;
```

### Visualization
```
Array:  [-2, 1, -3, 4, -1, 2, 1, -5, 4]
curSum:  -2  1  -2  4   3  5  6   1  5
                    ^────────────^
                    max subarray = [4,-1,2,1] sum=6

Decision at each element: "Am I better off alone, or extending previous?"
```

### Variants

| Variant | Modification |
|---------|-------------|
| Max Product Subarray | Track both maxProd AND minProd (negatives flip) |
| Min Subarray Sum | Flip signs or track minSum |
| Circular Max Subarray | max(normal Kadane, totalSum - minSubarray) |
| Subarray with at most K negatives | Sliding window hybrid |

### Max Product Variant
```java
int maxProd = nums[0], minProd = nums[0], result = nums[0];
for (int i = 1; i < n; i++) {
    if (nums[i] < 0) swap(maxProd, minProd);  // negative flips max/min
    maxProd = Math.max(nums[i], maxProd * nums[i]);
    minProd = Math.min(nums[i], minProd * nums[i]);
    result = Math.max(result, maxProd);
}
```

**Complexity:** O(n) time, O(1) space

---

## Pattern 2: Prefix Sum + HashMap

**When:** Count/find subarrays with exact sum K, sum divisible by K, equal 0s and 1s.

### Template
```java
Map<Integer, Integer> map = new HashMap<>();
map.put(0, 1);  // empty prefix has sum 0
int runningSum = 0, count = 0;

for (int num : nums) {
    runningSum += num;
    count += map.getOrDefault(runningSum - k, 0);
    map.merge(runningSum, 1, Integer::sum);
}
return count;
```

### Why It Works (Diagram)
```
prefix[0]  prefix[1]  prefix[2]  prefix[3]  prefix[4]  prefix[5]
  0          1          2          3          4          5
  
If prefix[j] - prefix[i] = k, then subarray (i, j] has sum k.
At each j, we ask: "How many previous prefix sums equal (prefix[j] - k)?"
That's exactly what the HashMap stores.
```

### Variants

| Problem | Key Insight |
|---------|-------------|
| Subarray Sum = K | Standard prefix sum + map |
| Subarray Divisible by K | Store (prefix % k) in map. Handle negative mod |
| Contiguous Array (0s=1s) | Convert 0 → -1, find subarray sum = 0 |
| Max Size Subarray Sum = K | Store first occurrence of prefix sum (not count) |
| Count Subarrays with XOR = K | prefix XOR instead of sum |

### 2D Prefix Sum Extension
```
pre[i][j] = sum of rectangle (0,0) to (i-1,j-1)
pre[i][j] = pre[i-1][j] + pre[i][j-1] - pre[i-1][j-1] + matrix[i-1][j-1]

sum(r1,c1 to r2,c2) = pre[r2+1][c2+1] - pre[r1][c2+1] - pre[r2+1][c1] + pre[r1][c1]
```

**Complexity:** O(n) time, O(n) space

---

## Pattern 3: Dutch National Flag (3-Way Partition)

**When:** Sort array of 3 distinct values in-place. Partition around pivot with 3 regions.

### Template
```java
int lo = 0, mid = 0, hi = n - 1;
while (mid <= hi) {
    if (arr[mid] == 0) { swap(arr, lo++, mid++); }
    else if (arr[mid] == 1) { mid++; }
    else { swap(arr, mid, hi--); }
}
```

### Invariant Diagram
```
[0, 0, 0, 1, 1, 1, ?, ?, ?, 2, 2, 2]
 ←─ 0s ─→ ←─ 1s ─→ ←unknown→ ←─ 2s ─→
          lo       mid        hi

After: all 0s | all 1s | all 2s
```

### Why mid doesn't increment on swap with hi:
The swapped element from `hi` is unknown - we haven't examined it yet. So `mid` stays to process it next iteration.

**Complexity:** O(n) time, O(1) space

---

## Pattern 4: Boyer-Moore Voting

**When:** Find majority element (> n/2) in O(1) space.

### Template
```java
int candidate = 0, count = 0;
for (int num : nums) {
    if (count == 0) candidate = num;
    count += (num == candidate) ? 1 : -1;
}
return candidate;  // verify with second pass if not guaranteed to exist
```

### Intuition
```
Think of it as "battle royale":
- Same element: reinforcements (+1)
- Different element: casualties on both sides (-1)
- Majority element always survives because it has > n/2 soldiers

[2, 2, 1, 1, 1, 2, 2]
 2(1) 2(2) 1(1) 1(0) 1(1) 2(0) 2(1)  → candidate = 2 ✓
```

### Variant: Elements appearing > n/3 (at most 2 such elements)
```java
int c1 = 0, c2 = 0, cnt1 = 0, cnt2 = 0;
for (int num : nums) {
    if (num == c1) cnt1++;
    else if (num == c2) cnt2++;
    else if (cnt1 == 0) { c1 = num; cnt1 = 1; }
    else if (cnt2 == 0) { c2 = num; cnt2 = 1; }
    else { cnt1--; cnt2--; }
}
// Verify c1, c2 with second pass
```

**Complexity:** O(n) time, O(1) space

---

## Pattern 5: Cyclic Sort / Index as Hash

**When:** Array of length n with values in [1..n]. Find missing, duplicate, first missing positive.

### Template
```java
// Place each number at its "correct" index: nums[i] should be i+1
for (int i = 0; i < n; i++) {
    while (nums[i] > 0 && nums[i] <= n && nums[nums[i] - 1] != nums[i]) {
        swap(nums, i, nums[i] - 1);
    }
}
// After: nums[i] != i+1 identifies the anomaly
```

### Problems Solved
```
FIRST MISSING POSITIVE: [3,4,-1,1]
  After cyclic sort: [1,-1,3,4]
  First i where nums[i] != i+1: i=1 → answer = 2

FIND DUPLICATE: [1,3,4,2,2]
  After cyclic sort: [1,2,3,4,2]
  nums[4] can't go to index 1 (occupied by same value) → duplicate = 2

FIND ALL MISSING: [4,3,2,7,8,2,3,1]
  After sort: [1,2,3,4,3,2,7,8]
  Indices 4,5 have wrong values → missing = {5, 6}
```

**Complexity:** O(n) time, O(1) space

---

## Pattern 6: Interval Merge / Overlap

**When:** Merge overlapping intervals, insert interval, find conflicts.

### Template
```java
Arrays.sort(intervals, (a, b) -> a[0] - b[0]);  // sort by start
List<int[]> merged = new ArrayList<>();
merged.add(intervals[0]);

for (int i = 1; i < intervals.length; i++) {
    int[] last = merged.get(merged.size() - 1);
    if (intervals[i][0] <= last[1]) {
        last[1] = Math.max(last[1], intervals[i][1]);  // merge
    } else {
        merged.add(intervals[i]);
    }
}
```

### Visualization
```
Input:  [1,3] [2,6] [8,10] [15,18]
         |-----|
         merged
Output: [1,6] [8,10] [15,18]

Insert [4,8] into [1,3],[6,9]:
  Before: [1,3]     After: [1,3],[4,9]
  Merge [4,8] with [6,9] → [4,9]
```

### Variant: Non-Overlapping Intervals (min removals)
```java
// Sort by END time, greedily keep non-overlapping
Arrays.sort(intervals, (a, b) -> a[1] - b[1]);
int end = Integer.MIN_VALUE, keep = 0;
for (int[] interval : intervals) {
    if (interval[0] >= end) { keep++; end = interval[1]; }
}
return n - keep;  // removals needed
```

**Complexity:** O(n log n) time, O(n) space

---

## Pattern 7: Two-Pass Left-Right

**When:** Each position needs information from both directions. No extra structure allowed.

### Template (Product Except Self)
```java
int[] result = new int[n];
// Left pass: result[i] = product of all elements to the left
result[0] = 1;
for (int i = 1; i < n; i++)
    result[i] = result[i-1] * nums[i-1];

// Right pass: multiply by product of all elements to the right
int right = 1;
for (int i = n - 2; i >= 0; i--) {
    right *= nums[i + 1];
    result[i] *= right;
}
```

### Also Used In
- **Trapping Rain Water:** leftMax[] and rightMax[] → water[i] = min(leftMax[i], rightMax[i]) - height[i]
- **Candy Distribution:** left pass (increasing), right pass (decreasing), take max
- **Stock Span:** Can be done with monotonic stack instead (more efficient)

**Complexity:** O(n) time, O(1) extra space (using output array)

---

## Pattern 8: Read/Write Pointer (In-Place Modification)

**When:** Remove duplicates, move elements, compact array.

### Template
```java
int write = 0;
for (int read = 0; read < n; read++) {
    if (condition(nums[read])) {
        nums[write] = nums[read];
        write++;
    }
}
return write;  // new effective length
```

### Examples
```
Move Zeroes [0,1,0,3,12]:
  condition: nums[read] != 0
  Result: [1,3,12,0,0], write=3

Remove Duplicates from Sorted [1,1,2,2,3]:
  condition: read==0 || nums[read] != nums[read-1]
  Result: [1,2,3,_,_], write=3

Remove Duplicates (allow 2) [1,1,1,2,2,3]:
  condition: write < 2 || nums[read] != nums[write-2]
  Result: [1,1,2,2,3,_], write=5
```

**Complexity:** O(n) time, O(1) space

---

## Summary Decision Flowchart

```
Array Problem?
│
├─ Subarray sum/count? ──────────→ Prefix Sum + HashMap
│
├─ Max/min subarray? ───────────→ Kadane's
│
├─ Values in [1..n]? ──────────→ Cyclic Sort / Index Hash
│
├─ Majority element? ──────────→ Boyer-Moore Voting
│
├─ 3-way partition? ───────────→ Dutch National Flag
│
├─ Intervals? ─────────────────→ Sort + Merge/Sweep
│
├─ Product/water/candy? ───────→ Two-Pass Left-Right
│
├─ In-place modify? ──────────→ Read/Write Pointer
│
└─ Rotate? ────────────────────→ Triple Reverse
```
