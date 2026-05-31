# Pattern 28: Divide and Conquer

## Core Philosophy

```
DIVIDE:    Break problem into smaller independent subproblems
CONQUER:   Solve subproblems recursively (base case terminates)
COMBINE:   Merge subproblem solutions into final answer
```

---

## Master Theorem Quick Reference

For recurrences of the form: **T(n) = aT(n/b) + O(n^d)**

| Case | Condition | Complexity |
|------|-----------|------------|
| 1 | d < log_b(a) | O(n^(log_b(a))) |
| 2 | d = log_b(a) | O(n^d * log n) |
| 3 | d > log_b(a) | O(n^d) |

**Examples:**
- Merge Sort: T(n) = 2T(n/2) + O(n) → a=2, b=2, d=1 → Case 2 → O(n log n)
- Binary Search: T(n) = T(n/2) + O(1) → a=1, b=2, d=0 → Case 2 → O(log n)
- Karatsuba: T(n) = 3T(n/2) + O(n) → a=3, b=2, d=1 → Case 1 → O(n^1.585)
- Strassen: T(n) = 7T(n/2) + O(n^2) → a=7, b=2, d=2 → Case 1 → O(n^2.807)

---

## D&C vs Dynamic Programming

| Aspect | Divide & Conquer | Dynamic Programming |
|--------|-----------------|-------------------|
| Subproblems | Independent, non-overlapping | Overlapping |
| Memoization | Not needed | Essential |
| Direction | Top-down recursive | Bottom-up (or memoized top-down) |
| Example | Merge Sort | Fibonacci |
| Combine step | Explicit merge | Table lookup |

**Decision:** If subproblems repeat → DP. If subproblems are fresh each time → D&C.

---

## Decision Flowchart

```
Problem has recursive structure?
├─ NO → Try greedy/iterative
└─ YES
   ├─ Subproblems overlap?
   │  ├─ YES → Use DP (memoize)
   │  └─ NO → Use D&C
   │     ├─ Can split into equal halves?
   │     │  ├─ YES → Merge Sort style (O(n log n))
   │     │  └─ NO → Partition style (Quick Select)
   │     ├─ Only one subproblem needed?
   │     │  ├─ YES → Binary Search / Decrease & Conquer
   │     │  └─ NO → Full D&C
   │     └─ Combine step complexity?
   │        ├─ O(1) → Total likely O(n) or O(log n)
   │        ├─ O(n) → Total likely O(n log n)
   │        └─ O(n^2) → Might not improve over brute force
```

---

## Pattern 1: Merge Sort (and Applications)

### Signal
- Need stable O(n log n) sort
- Count inversions / count relationships between elements across positions
- "Count smaller numbers after self"
- Any problem where answer depends on relative ordering across halves

### Template

```java
// Classic Merge Sort
void mergeSort(int[] arr, int left, int right) {
    if (left >= right) return;
    int mid = left + (right - left) / 2;
    mergeSort(arr, left, mid);
    mergeSort(arr, mid + 1, right);
    merge(arr, left, mid, right);
}

void merge(int[] arr, int left, int mid, int right) {
    int[] temp = new int[right - left + 1];
    int i = left, j = mid + 1, k = 0;
    while (i <= mid && j <= right) {
        if (arr[i] <= arr[j]) temp[k++] = arr[i++];
        else                   temp[k++] = arr[j++];
    }
    while (i <= mid) temp[k++] = arr[i++];
    while (j <= right) temp[k++] = arr[j++];
    System.arraycopy(temp, 0, arr, left, temp.length);
}
```

### Visualization

```
[38, 27, 43, 3, 9, 82, 10]

DIVIDE:
[38, 27, 43, 3]     |  [9, 82, 10]
[38, 27] | [43, 3]  |  [9, 82] | [10]
[38]|[27] [43]|[3]  |  [9]|[82]  [10]

CONQUER + COMBINE:
[27, 38] [3, 43]    |  [9, 82]   [10]
[3, 27, 38, 43]     |  [9, 10, 82]
[3, 9, 10, 27, 38, 43, 82]
```

### Variant 1: Count Inversions

```java
// Inversion: i < j but arr[i] > arr[j]
long countInversions(int[] arr, int left, int right) {
    if (left >= right) return 0;
    int mid = left + (right - left) / 2;
    long count = 0;
    count += countInversions(arr, left, mid);
    count += countInversions(arr, mid + 1, right);
    count += mergeCount(arr, left, mid, right);
    return count;
}

long mergeCount(int[] arr, int left, int mid, int right) {
    int[] temp = new int[right - left + 1];
    int i = left, j = mid + 1, k = 0;
    long inversions = 0;
    while (i <= mid && j <= right) {
        if (arr[i] <= arr[j]) {
            temp[k++] = arr[i++];
        } else {
            // All remaining elements in left half form inversions with arr[j]
            inversions += (mid - i + 1);
            temp[k++] = arr[j++];
        }
    }
    while (i <= mid) temp[k++] = arr[i++];
    while (j <= right) temp[k++] = arr[j++];
    System.arraycopy(temp, 0, arr, left, temp.length);
    return inversions;
}
```

### Variant 2: Count Smaller Numbers After Self (LC 315)

```java
// For each element, count how many smaller elements exist to its right
List<Integer> countSmaller(int[] nums) {
    int n = nums.length;
    int[] result = new int[n];
    int[] indices = new int[n]; // track original positions
    for (int i = 0; i < n; i++) indices[i] = i;
    mergeSortCount(nums, indices, result, 0, n - 1);
    List<Integer> res = new ArrayList<>();
    for (int r : result) res.add(r);
    return res;
}

void mergeSortCount(int[] nums, int[] indices, int[] result, int left, int right) {
    if (left >= right) return;
    int mid = left + (right - left) / 2;
    mergeSortCount(nums, indices, result, left, mid);
    mergeSortCount(nums, indices, result, mid + 1, right);
    
    int[] temp = new int[right - left + 1];
    int i = left, j = mid + 1, k = 0;
    int rightCount = 0; // elements taken from right half
    
    while (i <= mid && j <= right) {
        if (nums[indices[j]] < nums[indices[i]]) {
            rightCount++;
            temp[k++] = indices[j++];
        } else {
            result[indices[i]] += rightCount;
            temp[k++] = indices[i++];
        }
    }
    while (i <= mid) {
        result[indices[i]] += rightCount;
        temp[k++] = indices[i++];
    }
    while (j <= right) temp[k++] = indices[j++];
    System.arraycopy(temp, 0, indices, left, temp.length);
}
```

### Complexity
- Time: O(n log n)
- Space: O(n) auxiliary
- Recurrence: T(n) = 2T(n/2) + O(n)

---

## Pattern 2: Quick Sort / Quick Select

### Signal
- Find kth largest/smallest element in O(n) average
- Partition-based problems
- In-place sorting needed (cache-friendly)

### Template: Quick Sort

```java
void quickSort(int[] arr, int left, int right) {
    if (left >= right) return;
    int pivotIdx = partition(arr, left, right);
    quickSort(arr, left, pivotIdx - 1);
    quickSort(arr, pivotIdx + 1, right);
}

int partition(int[] arr, int left, int right) {
    // Randomized pivot to avoid worst case
    int randIdx = left + (int)(Math.random() * (right - left + 1));
    swap(arr, randIdx, right);
    
    int pivot = arr[right];
    int i = left; // boundary of elements <= pivot
    for (int j = left; j < right; j++) {
        if (arr[j] <= pivot) {
            swap(arr, i, j);
            i++;
        }
    }
    swap(arr, i, right);
    return i;
}
```

### Template: Quick Select (Kth Smallest)

```java
// Find kth smallest element (0-indexed) in O(n) average
int quickSelect(int[] arr, int left, int right, int k) {
    if (left == right) return arr[left];
    
    int pivotIdx = partition(arr, left, right);
    
    if (k == pivotIdx)      return arr[k];
    else if (k < pivotIdx)  return quickSelect(arr, left, pivotIdx - 1, k);
    else                    return quickSelect(arr, pivotIdx + 1, right, k);
}

// LC 215: Kth Largest Element
int findKthLargest(int[] nums, int k) {
    // kth largest = (n-k)th smallest (0-indexed)
    return quickSelect(nums, 0, nums.length - 1, nums.length - k);
}
```

### Visualization

```
Partition around pivot=4:
[3, 8, 2, 5, 1, 4, 7, 6]
                      ^pivot

i=0, j scans:
 j=0: 3<=4 → swap(0,0), i=1  [3, 8, 2, 5, 1, 4, 7, 6]
 j=1: 8>4  → skip            [3, 8, 2, 5, 1, 4, 7, 6]
 j=2: 2<=4 → swap(1,2), i=2  [3, 2, 8, 5, 1, 4, 7, 6]
 j=3: 5>4  → skip
 j=4: 1<=4 → swap(2,4), i=3  [3, 2, 1, 5, 8, 4, 7, 6]
 j=5: 4<=4 → swap(3,5), i=4  [3, 2, 1, 4, 8, 5, 7, 6]
 j=6: 7>4  → skip

Final swap(i=4, right=7):     [3, 2, 1, 4, 6, 5, 7, 8]
                                       ^pivot at idx 3

Quick Select for k=3: pivot at 3 = k → return arr[3] = 4
```

### Three-Way Partition (Dutch National Flag)

```java
// Handles duplicates efficiently for Quick Sort
void threeWayQuickSort(int[] arr, int left, int right) {
    if (left >= right) return;
    int pivot = arr[left + (int)(Math.random() * (right - left + 1))];
    int lt = left, gt = right, i = left;
    // Invariant: [left..lt-1] < pivot, [lt..i-1] == pivot, [gt+1..right] > pivot
    while (i <= gt) {
        if (arr[i] < pivot)      swap(arr, lt++, i++);
        else if (arr[i] > pivot) swap(arr, i, gt--);
        else                     i++;
    }
    threeWayQuickSort(arr, left, lt - 1);
    threeWayQuickSort(arr, gt + 1, right);
}
```

### Complexity
| Variant | Average | Worst | Space |
|---------|---------|-------|-------|
| Quick Sort | O(n log n) | O(n^2) | O(log n) stack |
| Quick Select | O(n) | O(n^2) | O(1) |
| Median of Medians | O(n) guaranteed | O(n) | O(n) |

---

## Pattern 3: Binary Search as D&C

### Signal
- Sorted array or monotonic search space
- "Find minimum/maximum satisfying condition"
- Eliminate half the search space each step

### Template

```java
// Classic binary search - decrease and conquer (one subproblem)
int binarySearch(int[] arr, int target) {
    int lo = 0, hi = arr.length - 1;
    while (lo <= hi) {
        int mid = lo + (hi - lo) / 2;
        if (arr[mid] == target) return mid;
        else if (arr[mid] < target) lo = mid + 1;
        else hi = mid - 1;
    }
    return -1; // not found
}

// Binary search on answer (parametric search)
int binarySearchOnAnswer(int lo, int hi) {
    while (lo < hi) {
        int mid = lo + (hi - lo) / 2;
        if (feasible(mid)) hi = mid;     // mid could be answer
        else               lo = mid + 1; // mid too small
    }
    return lo;
}
```

### Visualization

```
Search for 23 in [2, 5, 8, 12, 16, 23, 38, 56, 72, 91]

Step 1: lo=0, hi=9, mid=4 → arr[4]=16 < 23 → lo=5
Step 2: lo=5, hi=9, mid=7 → arr[7]=56 > 23 → hi=6
Step 3: lo=5, hi=6, mid=5 → arr[5]=23 = target → return 5

Recurrence: T(n) = T(n/2) + O(1) → O(log n)
```

### Complexity
- Time: O(log n)
- Space: O(1) iterative, O(log n) recursive
- Recurrence: T(n) = T(n/2) + O(1)

---

## Pattern 4: Maximum Subarray (D&C Approach)

### Signal
- Find contiguous subarray with maximum sum
- D&C approach useful for understanding; Kadane's is optimal iterative

### Template

```java
// D&C approach - O(n log n)
int maxSubArray(int[] nums, int left, int right) {
    if (left == right) return nums[left];
    
    int mid = left + (right - left) / 2;
    int leftMax = maxSubArray(nums, left, mid);
    int rightMax = maxSubArray(nums, mid + 1, right);
    int crossMax = maxCrossingSubarray(nums, left, mid, right);
    
    return Math.max(Math.max(leftMax, rightMax), crossMax);
}

int maxCrossingSubarray(int[] nums, int left, int mid, int right) {
    // Must include nums[mid] and nums[mid+1]
    int leftSum = Integer.MIN_VALUE, sum = 0;
    for (int i = mid; i >= left; i--) {
        sum += nums[i];
        leftSum = Math.max(leftSum, sum);
    }
    int rightSum = Integer.MIN_VALUE;
    sum = 0;
    for (int i = mid + 1; i <= right; i++) {
        sum += nums[i];
        rightSum = Math.max(rightSum, sum);
    }
    return leftSum + rightSum;
}

// Kadane's - O(n) - preferred in practice
int kadane(int[] nums) {
    int maxSoFar = nums[0], maxEndingHere = nums[0];
    for (int i = 1; i < nums.length; i++) {
        maxEndingHere = Math.max(nums[i], maxEndingHere + nums[i]);
        maxSoFar = Math.max(maxSoFar, maxEndingHere);
    }
    return maxSoFar;
}
```

### Visualization

```
[-2, 1, -3, 4, -1, 2, 1, -5, 4]

D&C split at mid=4:
Left:  [-2, 1, -3, 4, -1]  → max subarray = [4] = 4
Right: [2, 1, -5, 4]       → max subarray = [2,1] = 3
Cross: extends from mid both ways:
  Left from mid:  -1, 4-1=3, -3+3=0, 1+0=1, -2+1=-1 → best=3 (idx 3..4)
  Right from mid+1: 2, 2+1=3, 3-5=-2, -2+4=2 → best=3 (idx 5..6)
  Cross = 3 + 3 = 6 → [4, -1, 2, 1]

Answer: max(4, 3, 6) = 6
```

### Complexity
- D&C: O(n log n), T(n) = 2T(n/2) + O(n)
- Kadane's: O(n), O(1) space

---

## Pattern 5: Closest Pair of Points

### Signal
- Given n points in 2D plane, find minimum distance between any pair
- Brute force O(n^2), D&C achieves O(n log n)

### Template

```java
double closestPair(Point[] points) {
    // Pre-sort by x-coordinate
    Arrays.sort(points, (a, b) -> Double.compare(a.x, b.x));
    return closestUtil(points, 0, points.length - 1);
}

double closestUtil(Point[] points, int left, int right) {
    if (right - left < 3) {
        return bruteForce(points, left, right);
    }
    
    int mid = left + (right - left) / 2;
    double midX = points[mid].x;
    
    // Divide
    double dl = closestUtil(points, left, mid);
    double dr = closestUtil(points, mid + 1, right);
    double d = Math.min(dl, dr);
    
    // Combine: check strip of width 2d around midline
    List<Point> strip = new ArrayList<>();
    for (int i = left; i <= right; i++) {
        if (Math.abs(points[i].x - midX) < d) {
            strip.add(points[i]);
        }
    }
    
    // Sort strip by y-coordinate
    strip.sort((a, b) -> Double.compare(a.y, b.y));
    
    // Check at most 7 neighbors for each point in strip
    for (int i = 0; i < strip.size(); i++) {
        for (int j = i + 1; j < strip.size() && 
             (strip.get(j).y - strip.get(i).y) < d; j++) {
            d = Math.min(d, dist(strip.get(i), strip.get(j)));
        }
    }
    
    return d;
}

double dist(Point a, Point b) {
    return Math.sqrt((a.x - b.x) * (a.x - b.x) + (a.y - b.y) * (a.y - b.y));
}
```

### Visualization

```
Points: (2,3) (12,30) (40,50) (5,1) (12,10) (3,4)

1. Sort by x: (2,3) (3,4) (5,1) | (12,10) (12,30) (40,50)
                                  ^ midline x=5

2. Left half closest:  dist((2,3),(3,4)) = √2 ≈ 1.41
3. Right half closest: dist((12,10),(12,30)) = 20

4. d = min(1.41, 20) = 1.41

5. Strip (|x - 5| < 1.41): (5,1) (3,4)  → only 2 points
   dist((5,1),(3,4)) = √(4+9) = √13 ≈ 3.6 > d

6. Answer: 1.41 (points (2,3) and (3,4))
```

### Complexity
- Time: O(n log n) if strip sort is optimized (merge-based), O(n log^2 n) naive
- Space: O(n)
- Recurrence: T(n) = 2T(n/2) + O(n) [with optimized strip]

---

## Pattern 6: Median of Two Sorted Arrays

### Signal
- Two sorted arrays, find median in O(log(min(m,n)))
- Partition-based D&C on the smaller array

### Template

```java
// LC 4: Median of Two Sorted Arrays
double findMedianSortedArrays(int[] nums1, int[] nums2) {
    // Ensure nums1 is shorter
    if (nums1.length > nums2.length) return findMedianSortedArrays(nums2, nums1);
    
    int m = nums1.length, n = nums2.length;
    int lo = 0, hi = m;
    
    while (lo <= hi) {
        int i = lo + (hi - lo) / 2; // partition in nums1
        int j = (m + n + 1) / 2 - i; // partition in nums2
        
        int maxLeft1  = (i == 0) ? Integer.MIN_VALUE : nums1[i - 1];
        int minRight1 = (i == m) ? Integer.MAX_VALUE : nums1[i];
        int maxLeft2  = (j == 0) ? Integer.MIN_VALUE : nums2[j - 1];
        int minRight2 = (j == n) ? Integer.MAX_VALUE : nums2[j];
        
        if (maxLeft1 <= minRight2 && maxLeft2 <= minRight1) {
            // Correct partition found
            if ((m + n) % 2 == 0) {
                return (Math.max(maxLeft1, maxLeft2) + 
                        Math.min(minRight1, minRight2)) / 2.0;
            } else {
                return Math.max(maxLeft1, maxLeft2);
            }
        } else if (maxLeft1 > minRight2) {
            hi = i - 1; // move partition left in nums1
        } else {
            lo = i + 1; // move partition right in nums1
        }
    }
    throw new IllegalArgumentException();
}
```

### Visualization

```
nums1: [1, 3, 8, 9, 15]    m=5
nums2: [7, 11, 18, 19, 21, 25]  n=6
Total = 11 elements, median at position 6

Binary search on partition of nums1:
i=2, j=4: Left=[1,3 | 7,11,18,19]  Right=[8,9,15 | 21,25]
  maxLeft1=3, minRight1=8, maxLeft2=19, minRight2=21
  maxLeft2(19) > minRight1(8) → lo = 3

i=3, j=3: Left=[1,3,8 | 7,11,18]  Right=[9,15 | 19,21,25]
  maxLeft1=8, minRight1=9, maxLeft2=18, minRight2=19
  maxLeft2(18) > minRight1(9) → lo = 4

i=4, j=2: Left=[1,3,8,9 | 7,11]  Right=[15 | 18,19,21,25]
  maxLeft1=9, minRight1=15, maxLeft2=11, minRight2=18
  9<=18 ✓ and 11<=15 ✓ → Found!
  Odd total: median = max(9, 11) = 11
```

### Complexity
- Time: O(log(min(m, n)))
- Space: O(1)

---

## Pattern 7: Count of Range Sum

### Signal
- Count pairs (i, j) where lower <= prefixSum[j] - prefixSum[i] <= upper
- Merge sort on prefix sums to count valid ranges during merge

### Template

```java
// LC 327: Count of Range Sum
int countRangeSum(int[] nums, int lower, int upper) {
    int n = nums.length;
    long[] prefix = new long[n + 1];
    for (int i = 0; i < n; i++) {
        prefix[i + 1] = prefix[i] + nums[i];
    }
    return mergeSortCount(prefix, 0, n, lower, upper);
}

int mergeSortCount(long[] prefix, int left, int right, int lower, int upper) {
    if (left >= right) return 0;
    int mid = left + (right - left) / 2;
    int count = mergeSortCount(prefix, left, mid, lower, upper)
              + mergeSortCount(prefix, mid + 1, right, lower, upper);
    
    // Count: for each i in [left..mid], count j in [mid+1..right]
    // where lower <= prefix[j] - prefix[i] <= upper
    int j1 = mid + 1, j2 = mid + 1;
    for (int i = left; i <= mid; i++) {
        // Find range [j1, j2) where prefix[j] - prefix[i] in [lower, upper]
        while (j1 <= right && prefix[j1] - prefix[i] < lower) j1++;
        while (j2 <= right && prefix[j2] - prefix[i] <= upper) j2++;
        count += (j2 - j1);
    }
    
    // Standard merge
    long[] temp = new long[right - left + 1];
    int i = left, j = mid + 1, k = 0;
    while (i <= mid && j <= right) {
        if (prefix[i] <= prefix[j]) temp[k++] = prefix[i++];
        else temp[k++] = prefix[j++];
    }
    while (i <= mid) temp[k++] = prefix[i++];
    while (j <= right) temp[k++] = prefix[j++];
    System.arraycopy(temp, 0, prefix, left, temp.length);
    
    return count;
}
```

### Visualization

```
nums = [-2, 5, -1], lower = -2, upper = 2
prefix = [0, -2, 3, 2]

Merge sort on prefix array counts valid pairs:
  Range sums: [-2], [5], [-1], [-2,5]=3, [5,-1]=4, [-2,5,-1]=2
  Valid (in [-2,2]): [-2], [-1], [-2,5,-1]=2 → count = 3

During merge, for each i in left half, binary-search-style 
two pointers find valid j range in right half.
```

### Complexity
- Time: O(n log n)
- Space: O(n)

---

## Pattern 8: Different Ways to Add Parentheses

### Signal
- Expression with operators, compute all possible results from different groupings
- "Split at each operator" pattern
- Catalan number of possible structures

### Template

```java
// LC 241: Different Ways to Add Parentheses
List<Integer> diffWaysToCompute(String expression) {
    List<Integer> results = new ArrayList<>();
    
    for (int i = 0; i < expression.length(); i++) {
        char c = expression.charAt(i);
        if (c == '+' || c == '-' || c == '*') {
            // Split at operator i
            List<Integer> left = diffWaysToCompute(expression.substring(0, i));
            List<Integer> right = diffWaysToCompute(expression.substring(i + 1));
            
            // Combine all pairs
            for (int l : left) {
                for (int r : right) {
                    if (c == '+') results.add(l + r);
                    else if (c == '-') results.add(l - r);
                    else results.add(l * r);
                }
            }
        }
    }
    
    // Base case: entire string is a number
    if (results.isEmpty()) {
        results.add(Integer.parseInt(expression));
    }
    return results;
}

// Optimized with memoization (becomes D&C + memo = DP hybrid)
Map<String, List<Integer>> memo = new HashMap<>();

List<Integer> diffWaysToComputeMemo(String expression) {
    if (memo.containsKey(expression)) return memo.get(expression);
    List<Integer> results = new ArrayList<>();
    // ... same logic ...
    memo.put(expression, results);
    return results;
}
```

### Visualization

```
Expression: "2*3-4*5"

Split at each operator:
  At '*' (idx 1): "2" * "3-4*5"
  At '-' (idx 3): "2*3" - "4*5"
  At '*' (idx 5): "2*3-4" * "5"

"2*3" - "4*5":
  left = [6], right = [20]
  → [6-20] = [-14]

"2" * "3-4*5":
  "3-4*5" splits:
    "3" - "4*5" → 3-20 = -17
    "3-4" * "5" → -1*5 = -5
  left = [2], right = [-17, -5]
  → [2*-17, 2*-5] = [-34, -10]

Results: [-34, -14, -10, -10, 10]  (all possible evaluations)
```

### Complexity
- Time: O(Catalan(n)) where n = number of operators ≈ O(4^n / n^1.5)
- Space: O(Catalan(n)) for results
- With memo: significantly better for repeated subexpressions

---

## Pattern 9: Construct Binary Tree from Traversals

### Signal
- Given preorder + inorder (or postorder + inorder), reconstruct the tree
- Root identification + left/right subtree split

### Template: Preorder + Inorder

```java
// LC 105: Construct Binary Tree from Preorder and Inorder Traversal
Map<Integer, Integer> inorderMap = new HashMap<>();
int preIdx = 0;

TreeNode buildTree(int[] preorder, int[] inorder) {
    for (int i = 0; i < inorder.length; i++) {
        inorderMap.put(inorder[i], i);
    }
    return build(preorder, 0, inorder.length - 1);
}

TreeNode build(int[] preorder, int inLeft, int inRight) {
    if (inLeft > inRight) return null;
    
    int rootVal = preorder[preIdx++];
    TreeNode root = new TreeNode(rootVal);
    
    int inIdx = inorderMap.get(rootVal); // root position in inorder
    
    // MUST build left before right (preorder: root, LEFT, right)
    root.left = build(preorder, inLeft, inIdx - 1);
    root.right = build(preorder, inIdx + 1, inRight);
    
    return root;
}
```

### Template: Postorder + Inorder

```java
// LC 106: Construct Binary Tree from Inorder and Postorder Traversal
int postIdx;

TreeNode buildTreePost(int[] inorder, int[] postorder) {
    postIdx = postorder.length - 1;
    for (int i = 0; i < inorder.length; i++) {
        inorderMap.put(inorder[i], i);
    }
    return buildPost(postorder, 0, inorder.length - 1);
}

TreeNode buildPost(int[] postorder, int inLeft, int inRight) {
    if (inLeft > inRight) return null;
    
    int rootVal = postorder[postIdx--];
    TreeNode root = new TreeNode(rootVal);
    
    int inIdx = inorderMap.get(rootVal);
    
    // MUST build right before left (postorder consumed from end: root, RIGHT, left)
    root.right = buildPost(postorder, inIdx + 1, inRight);
    root.left = buildPost(postorder, inLeft, inIdx - 1);
    
    return root;
}
```

### Visualization

```
Preorder: [3, 9, 20, 15, 7]  (Root, Left, Right)
Inorder:  [9, 3, 15, 20, 7]  (Left, Root, Right)

Step 1: root = preorder[0] = 3
        inorder split: [9] | 3 | [15, 20, 7]
        
Step 2: Left subtree: pre=[9], in=[9]
        root = 9, leaf node
        
Step 3: Right subtree: pre=[20, 15, 7], in=[15, 20, 7]
        root = 20, split: [15] | 20 | [7]

Result:
        3
       / \
      9   20
         / \
        15   7
```

### Complexity
- Time: O(n) with HashMap for inorder index lookup
- Space: O(n) for HashMap + O(h) recursion stack

---

## Pattern 10: Pow(x, n) - Fast Exponentiation

### Signal
- Compute x^n efficiently
- Any "repeated squaring" problem
- Matrix exponentiation for Fibonacci, linear recurrences

### Template

```java
// LC 50: Pow(x, n)
double myPow(double x, int n) {
    long N = n; // handle Integer.MIN_VALUE
    if (N < 0) {
        x = 1 / x;
        N = -N;
    }
    return fastPow(x, N);
}

// Recursive
double fastPow(double x, long n) {
    if (n == 0) return 1.0;
    double half = fastPow(x, n / 2);
    if (n % 2 == 0) return half * half;
    else            return half * half * x;
}

// Iterative (binary exponentiation)
double fastPowIterative(double x, long n) {
    double result = 1.0;
    while (n > 0) {
        if ((n & 1) == 1) result *= x;
        x *= x;
        n >>= 1;
    }
    return result;
}
```

### Visualization

```
Compute 2^10:

Recursive:
  2^10 = (2^5)^2
  2^5  = (2^2)^2 * 2
  2^2  = (2^1)^2
  2^1  = (2^0)^2 * 2
  2^0  = 1

  Back-substitute: 1→2→4→32→1024
  Only 4 multiplications instead of 10!

Iterative (binary of 10 = 1010):
  n=10: bit=0, x=2→4,    result=1
  n=5:  bit=1, x=4→16,   result=1*4=4
  n=2:  bit=0, x=16→256,  result=4
  n=1:  bit=1, x=256→..., result=4*256=1024
```

### Matrix Exponentiation Extension

```java
// Fibonacci in O(log n) using matrix exponentiation
// [F(n+1), F(n)] = [[1,1],[1,0]]^n * [F(1), F(0)]
long fibonacci(int n) {
    if (n <= 1) return n;
    long[][] matrix = {{1, 1}, {1, 0}};
    long[][] result = matPow(matrix, n - 1);
    return result[0][0];
}

long[][] matPow(long[][] M, int n) {
    long[][] result = {{1, 0}, {0, 1}}; // identity
    while (n > 0) {
        if ((n & 1) == 1) result = matMul(result, M);
        M = matMul(M, M);
        n >>= 1;
    }
    return result;
}
```

### Complexity
- Time: O(log n)
- Space: O(log n) recursive, O(1) iterative

---

## Summary Table

| Pattern | Time | Space | Key Insight |
|---------|------|-------|-------------|
| Merge Sort | O(n log n) | O(n) | Stable; counting during merge |
| Quick Select | O(n) avg | O(1) | Only recurse on one side |
| Binary Search | O(log n) | O(1) | Eliminate half each step |
| Max Subarray D&C | O(n log n) | O(log n) | Cross-boundary case |
| Closest Pair | O(n log n) | O(n) | Strip has O(1) neighbors |
| Median Two Arrays | O(log min(m,n)) | O(1) | Partition balance |
| Range Sum Count | O(n log n) | O(n) | Merge sort on prefix sums |
| Add Parentheses | O(Catalan(n)) | O(Catalan(n)) | Split at every operator |
| Build Tree | O(n) | O(n) | Root splits inorder |
| Fast Power | O(log n) | O(1) | Square and multiply |

---

## Recurrence Relations Cheat Sheet

| Recurrence | Solution | Example |
|------------|----------|---------|
| T(n) = T(n/2) + O(1) | O(log n) | Binary Search |
| T(n) = T(n/2) + O(n) | O(n) | Quick Select (avg) |
| T(n) = 2T(n/2) + O(1) | O(n) | Tree traversal |
| T(n) = 2T(n/2) + O(n) | O(n log n) | Merge Sort |
| T(n) = 2T(n/2) + O(n log n) | O(n log^2 n) | Closest pair (naive) |
| T(n) = T(n-1) + O(n) | O(n^2) | Quick Sort (worst) |
| T(n) = T(n-1) + O(1) | O(n) | Linear recursion |
| T(n) = 2T(n-1) + O(1) | O(2^n) | Tower of Hanoi |

---

## Common Pitfalls

1. **Integer overflow in mid calculation**: Use `lo + (hi - lo) / 2` not `(lo + hi) / 2`
2. **Quick Sort worst case**: Always randomize pivot
3. **Merge sort stability**: Equal elements preserve order only if `<=` used (not `<`)
4. **Off-by-one in tree construction**: Preorder builds left-then-right; postorder builds right-then-left
5. **Pow edge case**: `n = Integer.MIN_VALUE` overflows when negated; cast to long first
6. **Closest pair strip**: Must check up to 7 neighbors, not all strip points
