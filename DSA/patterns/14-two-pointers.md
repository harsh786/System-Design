# 14 - Two Pointers

## Mental Model

Two pointers exploit **monotonic structure** (sorted order, directional invariants) to collapse O(n^2) brute-force into O(n) by eliminating entire regions of the search space with each pointer move.

---

## When to Use Two Pointers vs Alternatives

| Condition | Technique |
|-----------|-----------|
| Array is **sorted** (or can be sorted without losing info) | Two Pointers |
| Need **all pairs** or **count** with a target sum, unsorted | HashMap |
| Sorted + find **single element** | Binary Search |
| Need **subarray** of variable length with constraint | Sliding Window |
| Need **in-place** rearrangement / partition | Same-direction Two Pointers |

**Key Insight**: Two pointers works when moving one pointer in a direction **guarantees** the elimination of candidates.

---

## Visual: Converging vs Same-Direction

```
CONVERGING (Opposite Ends)
━━━━━━━━━━━━━━━━━━━━━━━━━━
  L ──────────────────► ◄──────────────────── R
  [1, 2, 3, 4, 5, 6, 7, 8, 9]
       L ────►     ◄──── R
            L ► ◄ R
              ▼
           MEET → done

SAME-DIRECTION (Fast-Slow)
━━━━━━━━━━━━━━━━━━━━━━━━━━
  slow
   ▼
  [0, 1, 0, 3, 12, 0, 0]
         fast ──────────────►

  slow writes "good" elements, fast scans all elements
```

---

## Decision Flowchart

```
                    ┌─────────────────────┐
                    │ Array/String problem │
                    └─────────┬───────────┘
                              │
                    ┌─────────▼───────────┐
                    │ Sorted or sortable?  │
                    └───┬─────────────┬───┘
                       YES            NO
                        │              │
              ┌─────────▼─────────┐   │  ┌──────────────────┐
              │ Pair/triplet sum? │   ├──► Partition/reorder │──► Same-Direction
              └───┬───────────┬───┘   │  └──────────────────┘
                 YES          NO      │
                  │            │      │  ┌──────────────────┐
    ┌─────────────▼──┐  ┌─────▼────┐ └──► Need all pairs?  │──► HashMap
    │ Converging     │  │ Merge    │     └──────────────────┘
    │ Two Pointers   │  │ Style    │
    └────────────────┘  └──────────┘
```

---

## Pattern 1: Opposite Ends / Converging

### Signal
- Sorted array + find pair with target sum/property
- Palindrome check
- "Two elements that satisfy condition"

### Template (Java)

```java
// Two Sum II - Input Array Is Sorted (LC 167)
public int[] twoSum(int[] nums, int target) {
    int lo = 0, hi = nums.length - 1;
    while (lo < hi) {
        int sum = nums[lo] + nums[hi];
        if (sum == target) return new int[]{lo + 1, hi + 1};
        else if (sum < target) lo++;
        else hi--;
    }
    return new int[]{-1, -1};
}

// Valid Palindrome (LC 125)
public boolean isPalindrome(String s) {
    int lo = 0, hi = s.length() - 1;
    while (lo < hi) {
        while (lo < hi && !Character.isLetterOrDigit(s.charAt(lo))) lo++;
        while (lo < hi && !Character.isLetterOrDigit(s.charAt(hi))) hi--;
        if (Character.toLowerCase(s.charAt(lo)) != Character.toLowerCase(s.charAt(hi)))
            return false;
        lo++;
        hi--;
    }
    return true;
}
```

### Visualization

```
Target = 9,  Array = [1, 2, 4, 6, 8, 10]

Step 1: L=0, R=5 → 1+10=11 > 9  → R--
Step 2: L=0, R=4 → 1+8=9  == 9  → FOUND
```

### Why It Works
- `sum < target` → `nums[lo] + nums[hi-1]` would be even smaller → must increase lo
- `sum > target` → `nums[lo+1] + nums[hi]` would be even larger → must decrease hi
- Each step eliminates an entire row/column of the pair matrix

### Complexity
- **Time**: O(n)
- **Space**: O(1)

---

## Pattern 2: Three Pointers / 3Sum

### Signal
- Find all triplets summing to target
- "Unique triplets" (duplicate skipping required)
- Reducible to fixing one element + Two Sum II

### Template (Java)

```java
// 3Sum (LC 15)
public List<List<Integer>> threeSum(int[] nums) {
    List<List<Integer>> res = new ArrayList<>();
    Arrays.sort(nums);
    
    for (int i = 0; i < nums.length - 2; i++) {
        // Skip duplicate anchors
        if (i > 0 && nums[i] == nums[i - 1]) continue;
        // Early termination: smallest triplet > 0
        if (nums[i] > 0) break;
        
        int lo = i + 1, hi = nums.length - 1;
        int target = -nums[i];
        
        while (lo < hi) {
            int sum = nums[lo] + nums[hi];
            if (sum == target) {
                res.add(Arrays.asList(nums[i], nums[lo], nums[hi]));
                // Skip duplicates on BOTH sides
                while (lo < hi && nums[lo] == nums[lo + 1]) lo++;
                while (lo < hi && nums[hi] == nums[hi - 1]) hi--;
                lo++;
                hi--;
            } else if (sum < target) {
                lo++;
            } else {
                hi--;
            }
        }
    }
    return res;
}
```

### Duplicate Skipping Strategy

```
Array: [-2, -2, 0, 0, 2, 2]

i=0: nums[i]=-2, find pair summing to 2 in [i+1..end]
     → found (0,2) → skip duplicate 0s and 2s
i=1: nums[1]==-2 == nums[0] → SKIP (would produce same triplets)
i=2: nums[i]=0, find pair summing to 0 in [i+1..end]
     → no valid pair
```

### Complexity
- **Time**: O(n^2)
- **Space**: O(1) excluding output (sort is in-place)

---

## Pattern 3: 4Sum / Generalized k-Sum

### Signal
- Find all k-tuples summing to target
- k > 3 but same dedup + converging logic applies

### Template (Java)

```java
// 4Sum (LC 18) - Generalized to kSum
public List<List<Integer>> fourSum(int[] nums, int target) {
    Arrays.sort(nums);
    return kSum(nums, (long) target, 0, 4);
}

private List<List<Integer>> kSum(int[] nums, long target, int start, int k) {
    List<List<Integer>> res = new ArrayList<>();
    
    if (start >= nums.length) return res;
    
    // Base case: 2Sum with two pointers
    if (k == 2) {
        int lo = start, hi = nums.length - 1;
        while (lo < hi) {
            long sum = (long) nums[lo] + nums[hi];
            if (sum == target) {
                res.add(new ArrayList<>(Arrays.asList(nums[lo], nums[hi])));
                while (lo < hi && nums[lo] == nums[lo + 1]) lo++;
                while (lo < hi && nums[hi] == nums[hi - 1]) hi--;
                lo++; hi--;
            } else if (sum < target) lo++;
            else hi--;
        }
        return res;
    }
    
    // Recursive case: fix one element, reduce to (k-1)Sum
    for (int i = start; i < nums.length - k + 1; i++) {
        if (i > start && nums[i] == nums[i - 1]) continue;
        
        // Pruning: check bounds
        long minSum = 0, maxSum = 0;
        for (int j = 0; j < k; j++) minSum += nums[i + j];
        for (int j = 0; j < k; j++) maxSum += nums[nums.length - 1 - j];
        if (minSum > target || maxSum < target) {
            if (minSum > target) break; // all future anchors are larger
            continue; // this anchor is too small, try next
        }
        
        for (List<Integer> subset : kSum(nums, target - nums[i], i + 1, k - 1)) {
            List<Integer> quad = new ArrayList<>();
            quad.add(nums[i]);
            quad.addAll(subset);
            res.add(quad);
        }
    }
    return res;
}
```

### Complexity
- **Time**: O(n^(k-1)) — for 4Sum: O(n^3)
- **Space**: O(k) recursion stack

---

## Pattern 4: Container With Most Water

### Signal
- Maximize area/product between two boundaries
- Both endpoints contribute, move the **limiting factor**

### Template (Java)

```java
// Container With Most Water (LC 11)
public int maxArea(int[] height) {
    int lo = 0, hi = height.length - 1;
    int maxWater = 0;
    
    while (lo < hi) {
        int w = hi - lo;
        int h = Math.min(height[lo], height[hi]);
        maxWater = Math.max(maxWater, w * h);
        
        // Move the shorter side — it's the bottleneck
        if (height[lo] < height[hi]) lo++;
        else hi--;
    }
    return maxWater;
}
```

### Why Move the Shorter Side?

```
height = [1, 8, 6, 2, 5, 4, 8, 3, 7]

L=0(h=1), R=8(h=7): area = min(1,7)*8 = 8
  Moving R inward: width decreases, height still capped at 1 → WORSE
  Moving L inward: width decreases, but height cap may INCREASE → POSSIBLE WIN
  
∴ Always move the pointer with smaller height
```

**Proof sketch**: If `height[lo] <= height[hi]`, then for any `hi' < hi`, `area(lo, hi') <= height[lo] * (hi-lo)` (current area). So all pairs `(lo, hi'), hi' < hi` are dominated → safe to advance lo.

### Complexity
- **Time**: O(n)
- **Space**: O(1)

---

## Pattern 5: Trapping Rain Water

### Signal
- Water trapped depends on min of left-max and right-max at each position
- Two pointers track `leftMax` and `rightMax` simultaneously

### Template (Java)

```java
// Trapping Rain Water (LC 42)
public int trap(int[] height) {
    int lo = 0, hi = height.length - 1;
    int leftMax = 0, rightMax = 0;
    int water = 0;
    
    while (lo < hi) {
        leftMax = Math.max(leftMax, height[lo]);
        rightMax = Math.max(rightMax, height[hi]);
        
        // Process the side with the LOWER max — it's the bottleneck
        if (leftMax < rightMax) {
            water += leftMax - height[lo];
            lo++;
        } else {
            water += rightMax - height[hi];
            hi--;
        }
    }
    return water;
}
```

### Visualization

```
height = [0, 1, 0, 2, 1, 0, 1, 3, 2, 1, 2, 1]

         3 │              █
         2 │        █ ░ ░ █ █ ░ █
         1 │  █ ░ █ █ ░ █ █ █ █ █
         0 │──█───█─█─█───█─█─█─█─█──
           0  1  2  3  4  5  6  7  8  9 10 11

Key insight at each step:
  if leftMax < rightMax:
    water at lo = leftMax - height[lo]  (guaranteed, right side is higher somewhere)
  else:
    water at hi = rightMax - height[hi] (guaranteed, left side is higher somewhere)
```

### Why It Works
- When `leftMax < rightMax`: we KNOW there exists a bar on the right >= rightMax > leftMax, so water at `lo` is bounded by `leftMax`.
- Mirror logic for the other side.

### Complexity
- **Time**: O(n)
- **Space**: O(1) — vs O(n) for prefix-max approach

---

## Pattern 6: Same Direction / Fast-Slow

### Signal
- In-place array modification (remove, deduplicate, partition)
- `slow` = write pointer (boundary of "processed" region)
- `fast` = read pointer (scans everything)

### Template (Java)

```java
// Remove Duplicates from Sorted Array (LC 26)
public int removeDuplicates(int[] nums) {
    if (nums.length == 0) return 0;
    int slow = 0; // last written position
    for (int fast = 1; fast < nums.length; fast++) {
        if (nums[fast] != nums[slow]) {
            slow++;
            nums[slow] = nums[fast];
        }
    }
    return slow + 1;
}

// Move Zeroes (LC 283)
public void moveZeroes(int[] nums) {
    int slow = 0; // next position for non-zero
    for (int fast = 0; fast < nums.length; fast++) {
        if (nums[fast] != 0) {
            // Swap to maintain relative order
            int tmp = nums[slow];
            nums[slow] = nums[fast];
            nums[fast] = tmp;
            slow++;
        }
    }
}

// Partition (Lomuto-style, used in QuickSort)
public int partition(int[] nums, int lo, int hi) {
    int pivot = nums[hi];
    int slow = lo; // boundary: everything before slow is < pivot
    for (int fast = lo; fast < hi; fast++) {
        if (nums[fast] < pivot) {
            swap(nums, slow, fast);
            slow++;
        }
    }
    swap(nums, slow, hi);
    return slow;
}
```

### Visualization

```
Move Zeroes: [0, 1, 0, 3, 12]

slow=0, fast=0: nums[0]=0  → skip
slow=0, fast=1: nums[1]=1  → swap(0,1) → [1,0,0,3,12], slow=1
slow=1, fast=2: nums[2]=0  → skip
slow=1, fast=3: nums[3]=3  → swap(1,3) → [1,3,0,0,12], slow=2
slow=2, fast=4: nums[4]=12 → swap(2,4) → [1,3,12,0,0], slow=3

Invariant: nums[0..slow-1] = processed non-zeros
           nums[slow..fast-1] = zeros
           nums[fast..end] = unprocessed
```

### Complexity
- **Time**: O(n)
- **Space**: O(1)

---

## Pattern 7: Two Arrays / Merge Style

### Signal
- Two sorted arrays, process in order
- Merge, intersection, union operations
- Each pointer advances through its own array

### Template (Java)

```java
// Merge Sorted Array (LC 88) — merge in-place from the END
public void merge(int[] nums1, int m, int[] nums2, int n) {
    int p1 = m - 1, p2 = n - 1, write = m + n - 1;
    
    while (p2 >= 0) {
        if (p1 >= 0 && nums1[p1] > nums2[p2]) {
            nums1[write--] = nums1[p1--];
        } else {
            nums1[write--] = nums2[p2--];
        }
    }
}

// Intersection of Two Sorted Arrays (unique elements)
public List<Integer> intersection(int[] a, int[] b) {
    // Assume sorted
    List<Integer> res = new ArrayList<>();
    int i = 0, j = 0;
    while (i < a.length && j < b.length) {
        if (a[i] < b[j]) i++;
        else if (a[i] > b[j]) j++;
        else {
            if (res.isEmpty() || res.get(res.size() - 1) != a[i])
                res.add(a[i]);
            i++;
            j++;
        }
    }
    return res;
}
```

### Key Insight: Merge from End
For LC 88, merging from the **end** avoids overwriting unprocessed elements — the extra space in `nums1` is at the tail.

```
nums1 = [1, 2, 3, _, _, _]  nums2 = [2, 5, 6]
                      write←
Compare 3 vs 6: write 6, p2--
Compare 3 vs 5: write 5, p2--
Compare 3 vs 2: write 3, p1--
Compare 2 vs 2: write 2, p2--
p2 < 0 → done: [1, 2, 2, 3, 5, 6]
```

### Complexity
- **Time**: O(m + n)
- **Space**: O(1) for in-place merge

---

## Pattern 8: Boats to Save People / Pair Matching

### Signal
- Pair heaviest with lightest if possible
- Greedy: maximize pairings under a constraint
- Sort + converging pointers

### Template (Java)

```java
// Boats to Save People (LC 881)
// Each boat carries at most 2 people, weight limit = limit
public int numRescueBoats(int[] people, int limit) {
    Arrays.sort(people);
    int lo = 0, hi = people.length - 1;
    int boats = 0;
    
    while (lo <= hi) {
        // Heaviest person always takes a boat
        if (lo == hi) {
            boats++;
            break;
        }
        // Can lightest pair with heaviest?
        if (people[lo] + people[hi] <= limit) {
            lo++; // lightest fits, pair them
        }
        hi--; // heaviest always boards
        boats++;
    }
    return boats;
}
```

### Why Greedy Works
- The heaviest person MUST go. Question is: can we fit the lightest with them?
- If lightest can't fit with heaviest, lightest can't fit with ANYONE heavier either → heaviest goes alone.
- If lightest CAN fit, pairing them is optimal (lightest has the best chance of pairing with anyone, so "using" them here doesn't hurt).

### Complexity
- **Time**: O(n log n) — dominated by sort
- **Space**: O(1)

---

## Pattern 9: Sort Colors / Dutch National Flag

### Signal
- Partition array into 3 regions (< pivot, == pivot, > pivot)
- Three pointers: `lo` (boundary of region 0), `mid` (scanner), `hi` (boundary of region 2)
- One-pass, in-place

### Template (Java)

```java
// Sort Colors (LC 75) — Dutch National Flag
public void sortColors(int[] nums) {
    int lo = 0;           // next position for 0
    int hi = nums.length - 1; // next position for 2
    int mid = 0;          // current scanner
    
    while (mid <= hi) {
        if (nums[mid] == 0) {
            swap(nums, lo, mid);
            lo++;
            mid++;
        } else if (nums[mid] == 2) {
            swap(nums, mid, hi);
            hi--;
            // DON'T advance mid — swapped element is unexamined
        } else { // nums[mid] == 1
            mid++;
        }
    }
}

private void swap(int[] a, int i, int j) {
    int tmp = a[i]; a[i] = a[j]; a[j] = tmp;
}
```

### Visualization

```
[2, 0, 2, 1, 1, 0]
 lo,mid          hi

Step 1: nums[mid]=2 → swap(mid,hi) → [0,0,2,1,1,2], hi--
        [0, 0, 2, 1, 1, 2]
         lo,mid       hi

Step 2: nums[mid]=0 → swap(lo,mid) → [0,...], lo++, mid++
        ...continues...

Invariant:
  [0..lo-1]   = all 0s
  [lo..mid-1] = all 1s
  [mid..hi]   = unprocessed
  [hi+1..end] = all 2s
```

### Why `mid` Doesn't Advance on Swap with `hi`
After swapping `nums[mid]` with `nums[hi]`, the new `nums[mid]` came from the unprocessed region — we haven't examined it yet. Must check it again.

### Complexity
- **Time**: O(n) — single pass
- **Space**: O(1)

---

## Summary Table

| # | Pattern | Key Idea | Time | Space |
|---|---------|----------|------|-------|
| 1 | Converging | Sorted + sum/pair → narrow from ends | O(n) | O(1) |
| 2 | 3Sum | Fix anchor + 2-pointer + dedup | O(n^2) | O(1) |
| 3 | k-Sum | Recursive: fix + reduce to (k-1)Sum | O(n^(k-1)) | O(k) |
| 4 | Container Water | Move shorter boundary (bottleneck) | O(n) | O(1) |
| 5 | Trap Rain Water | Process side with lower max | O(n) | O(1) |
| 6 | Fast-Slow | Write ptr + read ptr for in-place ops | O(n) | O(1) |
| 7 | Merge Style | One pointer per array, advance smaller | O(m+n) | O(1) |
| 8 | Pair Matching | Greedy pair heaviest with lightest | O(n log n) | O(1) |
| 9 | Dutch Flag | 3 regions, 3 pointers, single pass | O(n) | O(1) |

---

## Common Mistakes

1. **Off-by-one with `lo <= hi` vs `lo < hi`**: Use `lo < hi` when processing pairs; `lo <= hi` when `lo == hi` still needs processing (e.g., Dutch Flag scanner).

2. **Forgetting to skip duplicates AFTER finding a match** in 3Sum — leads to duplicate triplets.

3. **Advancing `mid` after swapping with `hi`** in Dutch Flag — the swapped-in element is unexamined.

4. **Integer overflow in 4Sum**: Use `(long)` casts when summing multiple elements.

5. **Modifying array when order matters**: Same-direction (swap-based) preserves relative order; converging does not.

---

## Practice Progression

```
Beginner:     LC 167 → LC 125 → LC 283 → LC 26
Intermediate: LC 15 → LC 11 → LC 75 → LC 88
Advanced:     LC 42 → LC 18 → LC 881 → LC 16 (3Sum Closest)
Expert:       LC 407 (3D Trap Water) → LC 838 → LC 923 (3Sum Multiplicity)
```
