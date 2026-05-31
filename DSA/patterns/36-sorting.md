# 36 - Sorting Algorithm Patterns

## Decision Flowchart

```
Need to sort?
├── Small n (< 50)? → Insertion Sort (Tim Sort uses this)
├── Need stability?
│   ├── Objects/records? → Merge Sort / Tim Sort
│   ├── Integers in small range? → Counting Sort
│   └── Large integers/strings? → Radix Sort (LSD)
├── Memory constrained (in-place)?
│   ├── Average case OK? → Quick Sort (randomized)
│   └── Worst case guarantee? → Heap Sort
├── Uniform distribution? → Bucket Sort
├── Nearly sorted? → Insertion Sort / Tim Sort
└── Linked List? → Merge Sort (no random access needed)
```

---

## Algorithm Selection Table

| Algorithm      | Best     | Average    | Worst      | Space   | Stable | In-Place | Notes                        |
|----------------|----------|------------|------------|---------|--------|----------|------------------------------|
| Merge Sort     | O(n lg n)| O(n lg n)  | O(n lg n)  | O(n)    | Yes    | No       | Predictable, parallelizable  |
| Quick Sort     | O(n lg n)| O(n lg n)  | O(n^2)     | O(lg n) | No     | Yes      | Cache-friendly, fast in practice |
| Heap Sort      | O(n lg n)| O(n lg n)  | O(n lg n)  | O(1)    | No     | Yes      | Guaranteed but slower constant |
| Tim Sort       | O(n)     | O(n lg n)  | O(n lg n)  | O(n)    | Yes    | No       | Java/Python default          |
| Counting Sort  | O(n+k)  | O(n+k)    | O(n+k)    | O(k)    | Yes    | No       | k = range of values          |
| Radix Sort     | O(d(n+k))| O(d(n+k)) | O(d(n+k)) | O(n+k)  | Yes    | No       | d = digits, k = base         |
| Bucket Sort    | O(n+k)  | O(n)      | O(n^2)    | O(n+k)  | Yes*   | No       | *If stable sub-sort          |
| Insertion Sort | O(n)     | O(n^2)    | O(n^2)    | O(1)    | Yes    | Yes      | Best for small/nearly sorted |

---

## Stability: Why It Matters

A sort is **stable** if equal elements retain their original relative order.

```
Input:  [(Alice, 90), (Bob, 85), (Carol, 90)]
Sort by score descending:
  Stable:   [(Alice, 90), (Carol, 90), (Bob, 85)]  ← Alice before Carol preserved
  Unstable: [(Carol, 90), (Alice, 90), (Bob, 85)]  ← order may flip
```

**When stability matters:**
- Multi-key sorting (sort by secondary key first, then primary)
- UI tables where user expects previous ordering preserved within ties
- Radix sort correctness depends on stable digit-sort subroutine

---

## Comparison-Based Lower Bound: O(n log n) Proof Sketch

Any comparison-based sort must distinguish between all n! permutations.
A binary decision tree with n! leaves needs height >= log2(n!).
By Stirling: log2(n!) = Theta(n log n).
Therefore: **No comparison-based sort can do better than O(n log n) in the worst case.**

Non-comparison sorts (Counting, Radix, Bucket) bypass this by exploiting value structure.

---

## Java Sort API Reference

```java
// Primitives: Dual-Pivot Quick Sort (not stable, O(n log n) avg, O(n^2) worst)
Arrays.sort(int[] a);
Arrays.sort(int[] a, int fromIndex, int toIndex);

// Objects: Tim Sort (stable, O(n log n) guaranteed)
Arrays.sort(T[] a, Comparator<? super T> c);
Collections.sort(List<T> list, Comparator<? super T> c);

// Parallel: Fork-join merge sort (Tim Sort parallel variant)
Arrays.parallelSort(int[] a);  // uses ForkJoinPool, threshold ~8192
```

**Key differences:**
- `Arrays.sort(int[])` — Dual-Pivot Quicksort (unstable) — primitives have no identity, stability irrelevant
- `Arrays.sort(Object[])` — Tim Sort (stable) — objects have identity, stability matters
- `Collections.sort()` — delegates to `Arrays.sort()` after `toArray()`

---

## 1. Merge Sort

### Signal
- Need stable O(n log n) sort
- Sorting linked lists
- Counting inversions
- External sort (data doesn't fit in memory)

### Template

```java
public class MergeSort {
    public void sort(int[] arr) {
        if (arr.length <= 1) return;
        int[] temp = new int[arr.length];
        mergeSort(arr, temp, 0, arr.length - 1);
    }

    private void mergeSort(int[] arr, int[] temp, int lo, int hi) {
        if (lo >= hi) return;
        int mid = lo + (hi - lo) / 2;
        mergeSort(arr, temp, lo, mid);
        mergeSort(arr, temp, mid + 1, hi);
        merge(arr, temp, lo, mid, hi);
    }

    private void merge(int[] arr, int[] temp, int lo, int mid, int hi) {
        // Optimization: skip merge if already sorted
        if (arr[mid] <= arr[mid + 1]) return;

        System.arraycopy(arr, lo, temp, lo, hi - lo + 1);
        int i = lo, j = mid + 1;
        for (int k = lo; k <= hi; k++) {
            if (i > mid)              arr[k] = temp[j++];
            else if (j > hi)          arr[k] = temp[i++];
            else if (temp[i] <= temp[j]) arr[k] = temp[i++]; // <= for stability
            else                      arr[k] = temp[j++];
        }
    }
}
```

### Visualization

```
[38, 27, 43, 3, 9, 82, 10]
         /              \
  [38, 27, 43, 3]    [9, 82, 10]
    /       \           /      \
[38, 27]  [43, 3]   [9, 82]  [10]
 /   \     /   \     /   \      |
[38] [27] [43] [3]  [9] [82]  [10]
 \   /     \   /     \   /      |
[27, 38]  [3, 43]   [9, 82]  [10]
    \       /           \      /
 [3, 27, 38, 43]    [9, 10, 82]
         \              /
  [3, 9, 10, 27, 38, 43, 82]
```

### Variant: Inversion Counting

```java
// An inversion is a pair (i,j) where i < j but arr[i] > arr[j]
public long countInversions(int[] arr) {
    int[] temp = new int[arr.length];
    return mergeSortCount(arr, temp, 0, arr.length - 1);
}

private long mergeSortCount(int[] arr, int[] temp, int lo, int hi) {
    if (lo >= hi) return 0;
    int mid = lo + (hi - lo) / 2;
    long count = 0;
    count += mergeSortCount(arr, temp, lo, mid);
    count += mergeSortCount(arr, temp, mid + 1, hi);
    count += mergeCount(arr, temp, lo, mid, hi);
    return count;
}

private long mergeCount(int[] arr, int[] temp, int lo, int mid, int hi) {
    System.arraycopy(arr, lo, temp, lo, hi - lo + 1);
    int i = lo, j = mid + 1;
    long count = 0;
    for (int k = lo; k <= hi; k++) {
        if (i > mid)              arr[k] = temp[j++];
        else if (j > hi)          arr[k] = temp[i++];
        else if (temp[i] <= temp[j]) arr[k] = temp[i++];
        else {
            // temp[j] < temp[i]: all elements from i..mid are inversions with j
            count += (mid - i + 1);
            arr[k] = temp[j++];
        }
    }
    return count;
}
```

### Complexity
- Time: O(n log n) all cases
- Space: O(n) auxiliary
- Stable: Yes

---

## 2. Quick Sort

### Signal
- General-purpose in-place sort
- Average case is sufficient (no worst-case guarantee needed)
- Cache-friendly performance desired
- Primitives (no stability requirement)

### Template: Lomuto Partition

```java
public class QuickSort {
    private Random rand = new Random();

    public void sort(int[] arr) {
        quickSort(arr, 0, arr.length - 1);
    }

    private void quickSort(int[] arr, int lo, int hi) {
        if (lo >= hi) return;
        int pivotIdx = partition(arr, lo, hi);
        quickSort(arr, lo, pivotIdx - 1);
        quickSort(arr, pivotIdx + 1, hi);
    }

    // Lomuto: pivot at end, single scan from left
    // Simple but O(n^2) on all-equal arrays
    private int partition(int[] arr, int lo, int hi) {
        // Randomize pivot to avoid worst case
        int randIdx = lo + rand.nextInt(hi - lo + 1);
        swap(arr, randIdx, hi);

        int pivot = arr[hi];
        int i = lo - 1; // boundary of elements <= pivot
        for (int j = lo; j < hi; j++) {
            if (arr[j] <= pivot) {
                i++;
                swap(arr, i, j);
            }
        }
        swap(arr, i + 1, hi);
        return i + 1;
    }

    private void swap(int[] arr, int a, int b) {
        int tmp = arr[a]; arr[a] = arr[b]; arr[b] = tmp;
    }
}
```

### Template: Hoare Partition

```java
// Hoare: two pointers from both ends, fewer swaps in practice
private int hoarePartition(int[] arr, int lo, int hi) {
    int pivot = arr[lo + (hi - lo) / 2]; // median element as pivot
    int i = lo - 1, j = hi + 1;
    while (true) {
        do { i++; } while (arr[i] < pivot);
        do { j--; } while (arr[j] > pivot);
        if (i >= j) return j; // NOTE: returns j, not pivot position
        swap(arr, i, j);
    }
}

// With Hoare, recurse on [lo, p] and [p+1, hi]
private void quickSortHoare(int[] arr, int lo, int hi) {
    if (lo >= hi) return;
    int p = hoarePartition(arr, lo, hi);
    quickSortHoare(arr, lo, p);     // include p
    quickSortHoare(arr, p + 1, hi);
}
```

### Lomuto vs Hoare

| Aspect          | Lomuto                    | Hoare                      |
|-----------------|---------------------------|----------------------------|
| Swaps           | More (every <= element)   | Fewer (~n/6 on random)     |
| Equal elements  | O(n^2) without 3-way      | Handles better naturally   |
| Implementation  | Simpler                   | Trickier boundary cases    |
| Pivot position  | Known after partition     | Not at final position      |
| Use case        | Teaching, Quick Select    | Production quick sort      |

### Visualization (Lomuto)

```
[3, 6, 8, 10, 1, 2, 1]  pivot=1(random picked, swapped to end)
                          i=-1, scan j=0..5
After partition: [1, 1, ...rest..., pivot_in_place]

Full trace with pivot = arr[hi] = 1 (after swap):
 j=0: 3>1, skip
 j=1: 6>1, skip
 ...
 (elements <= 1 accumulate at front)
```

### Complexity
- Time: O(n log n) average, O(n^2) worst (mitigated by randomization)
- Space: O(log n) stack (O(n) worst case without tail-call optimization)
- Stable: No (swaps non-adjacent elements)

---

## 3. Quick Select (Kth Smallest Element)

### Signal
- Find kth smallest/largest element
- Don't need full sort
- O(n) average time desired
- Top-K problems where heap is too slow

### Template

```java
public int quickSelect(int[] arr, int k) {
    // k is 0-indexed: 0 = smallest, n-1 = largest
    return select(arr, 0, arr.length - 1, k);
}

private Random rand = new Random();

private int select(int[] arr, int lo, int hi, int k) {
    if (lo == hi) return arr[lo];

    int pivotIdx = lomutoPartition(arr, lo, hi);

    if (pivotIdx == k) return arr[k];
    else if (pivotIdx < k) return select(arr, pivotIdx + 1, hi, k);
    else return select(arr, lo, pivotIdx - 1, k);
}

private int lomutoPartition(int[] arr, int lo, int hi) {
    int randIdx = lo + rand.nextInt(hi - lo + 1);
    swap(arr, randIdx, hi);
    int pivot = arr[hi];
    int i = lo - 1;
    for (int j = lo; j < hi; j++) {
        if (arr[j] <= pivot) {
            swap(arr, ++i, j);
        }
    }
    swap(arr, i + 1, hi);
    return i + 1;
}
```

### Visualization

```
Find 3rd smallest (k=2) in [7, 10, 4, 3, 20, 15]

Partition around random pivot (say 7):
  [4, 3, | 7 | 10, 20, 15]
  pivotIdx = 2 == k → return 7

If k=4, pivot at 2: k > pivotIdx → recurse right [10, 20, 15]
```

### Complexity
- Time: O(n) average, O(n^2) worst
- Space: O(1) iterative / O(log n) recursive
- Note: Modifies input array. Use `introselect` for guaranteed O(n).

---

## 4. Heap Sort

### Signal
- Need in-place O(n log n) guaranteed
- Memory is critical (no O(n) auxiliary allowed)
- Don't need stability
- Building a priority queue anyway

### Template

```java
public void heapSort(int[] arr) {
    int n = arr.length;

    // Phase 1: Build max-heap (bottom-up, O(n))
    for (int i = n / 2 - 1; i >= 0; i--) {
        heapify(arr, n, i);
    }

    // Phase 2: Extract max repeatedly
    for (int i = n - 1; i > 0; i--) {
        swap(arr, 0, i);       // move max to end
        heapify(arr, i, 0);    // restore heap on reduced size
    }
}

// Sift down: ensure subtree rooted at i is a max-heap
private void heapify(int[] arr, int heapSize, int i) {
    int largest = i;
    int left = 2 * i + 1;
    int right = 2 * i + 2;

    if (left < heapSize && arr[left] > arr[largest])
        largest = left;
    if (right < heapSize && arr[right] > arr[largest])
        largest = right;

    if (largest != i) {
        swap(arr, i, largest);
        heapify(arr, heapSize, largest);
    }
}
```

### Visualization

```
Array: [4, 10, 3, 5, 1]

Build max-heap (heapify from n/2-1 down to 0):
       4              10
      / \    →       /  \
    10    3        5     3
   / \            / \
  5   1          4   1

Extract phase:
[10,5,3,4,1] → swap(0,4) → [1,5,3,4,|10] → heapify → [5,4,3,1,|10]
[5,4,3,1|10] → swap(0,3) → [1,4,3,|5,10] → heapify → [4,1,3,|5,10]
...continues until sorted
```

### Complexity
- Time: O(n log n) all cases (build heap O(n) + n extractions O(log n) each)
- Space: O(1) in-place
- Stable: No (long-distance swaps)
- Note: Poor cache locality compared to Quick Sort

---

## 5. Counting Sort

### Signal
- Values are integers in a known, small range [0, k]
- k = O(n) for linear time benefit
- Need stability (prerequisite for Radix Sort)
- Example: sort ages (0-150), sort characters (0-127)

### Template

```java
public int[] countingSort(int[] arr, int maxVal) {
    int[] count = new int[maxVal + 1];
    int[] output = new int[arr.length];

    // Count occurrences
    for (int x : arr) count[x]++;

    // Prefix sum (count[i] = number of elements <= i)
    for (int i = 1; i <= maxVal; i++) count[i] += count[i - 1];

    // Build output (traverse RIGHT to LEFT for stability)
    for (int i = arr.length - 1; i >= 0; i--) {
        output[count[arr[i]] - 1] = arr[i];
        count[arr[i]]--;
    }
    return output;
}

// Simplified version when you only need sorted values (not stability)
public void countingSortSimple(int[] arr, int maxVal) {
    int[] count = new int[maxVal + 1];
    for (int x : arr) count[x]++;
    int idx = 0;
    for (int val = 0; val <= maxVal; val++) {
        while (count[val]-- > 0) arr[idx++] = val;
    }
}
```

### Visualization

```
arr = [4, 2, 2, 8, 3, 3, 1]  maxVal = 8

Count:   [0, 1, 2, 2, 1, 0, 0, 0, 1]  (index = value)
Prefix:  [0, 1, 3, 5, 6, 6, 6, 6, 7]  (cumulative)

Build output (right to left):
  arr[6]=1: output[count[1]-1] = output[0] = 1, count[1]=0
  arr[5]=3: output[count[3]-1] = output[4] = 3, count[3]=4
  arr[4]=3: output[count[3]-1] = output[3] = 3, count[3]=3
  ...
Output: [1, 2, 2, 3, 3, 4, 8]
```

### Complexity
- Time: O(n + k) where k = range
- Space: O(n + k)
- Stable: Yes (right-to-left placement preserves order)
- Not comparison-based: bypasses O(n log n) lower bound

---

## 6. Radix Sort

### Signal
- Integers or fixed-length strings
- d digits, each in range [0, k-1]
- O(d * (n + k)) which is O(n) when d and k are constants
- Need stable sort on large integers without comparison overhead

### Template: LSD (Least Significant Digit First)

```java
public void radixSort(int[] arr) {
    int max = Arrays.stream(arr).max().orElse(0);

    // Sort by each digit position (1, 10, 100, ...)
    for (int exp = 1; max / exp > 0; exp *= 10) {
        countingSortByDigit(arr, exp);
    }
}

private void countingSortByDigit(int[] arr, int exp) {
    int n = arr.length;
    int[] output = new int[n];
    int[] count = new int[10]; // digits 0-9

    for (int x : arr) count[(x / exp) % 10]++;
    for (int i = 1; i < 10; i++) count[i] += count[i - 1];

    // Right to left for stability
    for (int i = n - 1; i >= 0; i--) {
        int digit = (arr[i] / exp) % 10;
        output[count[digit] - 1] = arr[i];
        count[digit]--;
    }
    System.arraycopy(output, 0, arr, 0, n);
}
```

### LSD vs MSD

| Aspect   | LSD (Least Significant First) | MSD (Most Significant First) |
|----------|-------------------------------|------------------------------|
| Direction| Process rightmost digit first | Process leftmost digit first |
| Approach | Iterative, sort all together  | Recursive, partition into buckets |
| Stability| Naturally stable              | Needs care                   |
| Use case | Fixed-length integers         | Variable-length strings, early termination |
| Example  | Sort phone numbers            | Sort dictionary words        |

### Visualization (LSD)

```
Input: [170, 45, 75, 90, 802, 24, 2, 66]

Sort by ones digit:  [170, 90, 802, 2, 24, 45, 75, 66]
Sort by tens digit:  [802, 2, 24, 45, 66, 170, 75, 90]
Sort by hundreds:    [2, 24, 45, 66, 75, 90, 170, 802]
```

### Complexity
- Time: O(d * (n + k)), d = digits, k = base (10 for decimal)
- Space: O(n + k)
- Stable: Yes (LSD relies on stable sub-sort)
- When to use: n large, d small, k small (e.g., 32-bit ints: d=10 digits base 10, or d=4 bytes base 256)

---

## 7. Bucket Sort

### Signal
- Input uniformly distributed over a range (e.g., [0.0, 1.0))
- Can create n buckets and distribute evenly
- O(n) average when distribution is uniform

### Template

```java
public void bucketSort(float[] arr) {
    int n = arr.length;
    if (n <= 1) return;

    // Create n empty buckets
    List<List<Float>> buckets = new ArrayList<>();
    for (int i = 0; i < n; i++) buckets.add(new ArrayList<>());

    // Distribute elements into buckets
    for (float x : arr) {
        int bucketIdx = (int) (x * n); // assumes x in [0, 1)
        if (bucketIdx == n) bucketIdx--; // edge case for x = 1.0
        buckets.get(bucketIdx).add(x);
    }

    // Sort each bucket (insertion sort for small buckets)
    for (List<Float> bucket : buckets) {
        Collections.sort(bucket);
    }

    // Concatenate
    int idx = 0;
    for (List<Float> bucket : buckets) {
        for (float x : bucket) arr[idx++] = x;
    }
}

// Generic version for integer range [minVal, maxVal]
public void bucketSortRange(int[] arr, int minVal, int maxVal) {
    int n = arr.length;
    int bucketCount = n;
    int range = maxVal - minVal + 1;
    List<List<Integer>> buckets = new ArrayList<>();
    for (int i = 0; i < bucketCount; i++) buckets.add(new ArrayList<>());

    for (int x : arr) {
        int idx = (int) ((long)(x - minVal) * bucketCount / range);
        buckets.get(idx).add(x);
    }

    int pos = 0;
    for (List<Integer> bucket : buckets) {
        Collections.sort(bucket);
        for (int x : bucket) arr[pos++] = x;
    }
}
```

### Complexity
- Time: O(n) average (uniform distribution), O(n^2) worst (all in one bucket)
- Space: O(n + k) where k = number of buckets
- Stable: Yes if sub-sort is stable

---

## 8. Tim Sort Concept

### Signal
- Real-world data often has "runs" (pre-sorted subsequences)
- Java's `Arrays.sort(Object[])` and Python's `sorted()`
- Best of both worlds: merge sort's guarantee + insertion sort's speed on small/sorted data

### How It Works

```
1. Divide array into "runs" (minimum run size ~32-64)
2. If natural run is shorter than minRun, extend with insertion sort
3. Push runs onto a stack
4. Merge runs using invariants:
   - run[i-2] > run[i-1] + run[i]
   - run[i-1] > run[i]
   (ensures balanced merges like Fibonacci)
5. Merge uses "galloping mode" when one run consistently wins
```

### Key Optimizations
- **Minimum run size:** Chosen so total merges are a power of 2 (32-64)
- **Galloping mode:** Binary search for merge insertion point when one side dominates
- **Existing order detection:** Detects ascending and descending runs (reverses descending)
- **Merge optimization:** Only allocate temp for the smaller of two runs being merged

### Pseudocode

```java
// Conceptual Tim Sort
public void timSort(int[] arr) {
    int n = arr.length;
    int MIN_RUN = computeMinRun(n); // typically 32-64

    // Step 1: Sort small runs with insertion sort
    for (int i = 0; i < n; i += MIN_RUN) {
        int end = Math.min(i + MIN_RUN - 1, n - 1);
        insertionSort(arr, i, end);
    }

    // Step 2: Merge runs, doubling size each pass
    for (int size = MIN_RUN; size < n; size *= 2) {
        for (int lo = 0; lo < n; lo += 2 * size) {
            int mid = Math.min(lo + size - 1, n - 1);
            int hi = Math.min(lo + 2 * size - 1, n - 1);
            if (mid < hi) merge(arr, lo, mid, hi);
        }
    }
}

private int computeMinRun(int n) {
    int r = 0;
    while (n >= 64) { r |= (n & 1); n >>= 1; }
    return n + r;
}
```

### Complexity
- Time: O(n) best (already sorted), O(n log n) worst
- Space: O(n)
- Stable: Yes

---

## 9. Custom Comparators

### Signal
- Sort objects by custom criteria
- Multi-key sorting
- Reverse order, null handling
- Lexicographic tricks (a+b vs b+a)

### Template: Java Patterns

```java
// Lambda basics
Arrays.sort(arr, (a, b) -> a - b);           // ascending (DANGER: overflow)
Arrays.sort(arr, (a, b) -> Integer.compare(a, b)); // safe ascending
Arrays.sort(arr, (a, b) -> Integer.compare(b, a)); // descending

// Comparator chains (multi-key)
Arrays.sort(people, Comparator
    .comparingInt(Person::getAge)
    .thenComparing(Person::getName)
    .thenComparingDouble(Person::getSalary)
    .reversed());

// Sort 2D array by first element, then by second descending
Arrays.sort(intervals, (a, b) -> 
    a[0] != b[0] ? Integer.compare(a[0], b[0]) : Integer.compare(b[1], a[1]));

// Null-safe
Comparator.nullsFirst(Comparator.naturalOrder());
Comparator.nullsLast(Comparator.comparingInt(String::length));
```

### Common Pitfall: Integer Overflow

```java
// WRONG: overflows when a = Integer.MIN_VALUE, b = 1
(a, b) -> a - b

// CORRECT:
(a, b) -> Integer.compare(a, b)
```

---

## 10. Sort Applications

### 10.1 Largest Number (LC 179)

```java
// Given [3, 30, 34, 5, 9] → "9534330"
public String largestNumber(int[] nums) {
    String[] strs = new String[nums.length];
    for (int i = 0; i < nums.length; i++) strs[i] = String.valueOf(nums[i]);

    // Compare: which concatenation is larger?
    Arrays.sort(strs, (a, b) -> (b + a).compareTo(a + b));

    if (strs[0].equals("0")) return "0";  // edge case: all zeros
    return String.join("", strs);
}
// Why this works: defines a total order where a+b > b+a means a should come first
// Transitivity proof: if a○b > b○a and b○c > c○b, then a○c > c○a
```

### 10.2 Meeting Rooms (LC 252, 253)

```java
// Can attend all meetings? (no overlap)
public boolean canAttendMeetings(int[][] intervals) {
    Arrays.sort(intervals, (a, b) -> Integer.compare(a[0], b[0]));
    for (int i = 1; i < intervals.length; i++) {
        if (intervals[i][0] < intervals[i - 1][1]) return false;
    }
    return true;
}

// Minimum meeting rooms needed (LC 253)
public int minMeetingRooms(int[][] intervals) {
    int n = intervals.length;
    int[] starts = new int[n], ends = new int[n];
    for (int i = 0; i < n; i++) {
        starts[i] = intervals[i][0];
        ends[i] = intervals[i][1];
    }
    Arrays.sort(starts);
    Arrays.sort(ends);

    int rooms = 0, endPtr = 0;
    for (int i = 0; i < n; i++) {
        if (starts[i] < ends[endPtr]) rooms++;
        else endPtr++;
    }
    return rooms;
}
```

### 10.3 Merge Intervals (LC 56)

```java
public int[][] merge(int[][] intervals) {
    Arrays.sort(intervals, (a, b) -> Integer.compare(a[0], b[0]));
    List<int[]> merged = new ArrayList<>();
    merged.add(intervals[0]);

    for (int i = 1; i < intervals.length; i++) {
        int[] last = merged.get(merged.size() - 1);
        if (intervals[i][0] <= last[1]) {
            last[1] = Math.max(last[1], intervals[i][1]);
        } else {
            merged.add(intervals[i]);
        }
    }
    return merged.toArray(new int[0][]);
}
```

### 10.4 H-Index (LC 274)

```java
// h = largest value where h papers have >= h citations
public int hIndex(int[] citations) {
    Arrays.sort(citations);
    int n = citations.length;
    for (int i = 0; i < n; i++) {
        int h = n - i; // papers with >= citations[i] citations
        if (citations[i] >= h) return h;
    }
    return 0;
}

// O(n) with counting sort since citations[i] <= n matters
public int hIndexLinear(int[] citations) {
    int n = citations.length;
    int[] count = new int[n + 1]; // bucket: count[i] = papers with exactly i citations
    for (int c : citations) count[Math.min(c, n)]++;

    int papers = 0;
    for (int h = n; h >= 0; h--) {
        papers += count[h];
        if (papers >= h) return h;
    }
    return 0;
}
```

### 10.5 Wiggle Sort (LC 324)

```java
// Rearrange: nums[0] < nums[1] > nums[2] < nums[3] > ...
public void wiggleSort(int[] nums) {
    int n = nums.length;
    int median = quickSelect(nums, n / 2); // find median

    // 3-way partition around median with index mapping
    // Virtual index: maps i → (1+2*i) % (n|1)
    // Places larger elements at odd indices, smaller at even
    int left = 0, right = n - 1, i = 0;
    while (i <= right) {
        int idx = newIndex(i, n);
        if (nums[idx] > median) {
            swap(nums, newIndex(left++, n), idx);
            i++;
        } else if (nums[idx] < median) {
            swap(nums, idx, newIndex(right--, n));
        } else {
            i++;
        }
    }
}

private int newIndex(int i, int n) {
    return (1 + 2 * i) % (n | 1);
}
```

---

## 11. Dutch National Flag / 3-Way Partition (LC 75)

### Signal
- Sort array with only 3 distinct values
- Partition around a pivot into < , = , > regions
- Single pass O(n), O(1) space

### Template

```java
// Sort Colors: 0=red, 1=white, 2=blue
public void sortColors(int[] nums) {
    int lo = 0, mid = 0, hi = nums.length - 1;

    while (mid <= hi) {
        if (nums[mid] == 0) {
            swap(nums, lo++, mid++);
        } else if (nums[mid] == 1) {
            mid++;
        } else { // nums[mid] == 2
            swap(nums, mid, hi--);
            // Don't increment mid: swapped element needs inspection
        }
    }
}

// Generic 3-way partition around pivot value
public void threeWayPartition(int[] arr, int pivot) {
    int lo = 0, mid = 0, hi = arr.length - 1;
    while (mid <= hi) {
        if (arr[mid] < pivot)      swap(arr, lo++, mid++);
        else if (arr[mid] == pivot) mid++;
        else                        swap(arr, mid, hi--);
    }
}
```

### Visualization

```
[2, 0, 2, 1, 1, 0]
 lo,mid           hi

Step 1: nums[mid]=2 → swap(mid,hi), hi--
[0, 0, 2, 1, 1, 2]  lo=0, mid=0, hi=4

Step 2: nums[mid]=0 → swap(lo,mid), lo++, mid++
[0, 0, 2, 1, 1, 2]  lo=1, mid=1, hi=4

Step 3: nums[mid]=0 → swap(lo,mid), lo++, mid++
[0, 0, 2, 1, 1, 2]  lo=2, mid=2, hi=4

Step 4: nums[mid]=2 → swap(mid,hi), hi--
[0, 0, 1, 1, 2, 2]  lo=2, mid=2, hi=3

Step 5: nums[mid]=1 → mid++
[0, 0, 1, 1, 2, 2]  lo=2, mid=3, hi=3

Step 6: nums[mid]=1 → mid++
mid=4 > hi=3 → DONE

Result: [0, 0, 1, 1, 2, 2]
```

### Complexity
- Time: O(n) single pass
- Space: O(1)
- Invariant: `[0..lo-1]=0 | [lo..mid-1]=1 | [mid..hi]=unknown | [hi+1..n-1]=2`

---

## 12. Pancake Sort (LC 969)

### Signal
- Only operation allowed: flip first k elements (reverse prefix)
- Sort using minimum flips
- Not practical but tests algorithmic thinking

### Template

```java
public List<Integer> pancakeSort(int[] arr) {
    List<Integer> flips = new ArrayList<>();
    int n = arr.length;

    for (int size = n; size > 1; size--) {
        // Find index of max element in arr[0..size-1]
        int maxIdx = 0;
        for (int i = 1; i < size; i++) {
            if (arr[i] > arr[maxIdx]) maxIdx = i;
        }

        if (maxIdx == size - 1) continue; // already in place

        // Flip max to front (if not already there)
        if (maxIdx != 0) {
            flip(arr, maxIdx + 1);
            flips.add(maxIdx + 1);
        }

        // Flip max to its correct position
        flip(arr, size);
        flips.add(size);
    }
    return flips;
}

private void flip(int[] arr, int k) {
    int lo = 0, hi = k - 1;
    while (lo < hi) {
        int tmp = arr[lo]; arr[lo] = arr[hi]; arr[hi] = tmp;
        lo++; hi--;
    }
}
```

### Algorithm
1. Find max in unsorted portion
2. Flip it to front
3. Flip it to its final position (end of unsorted portion)
4. Repeat for next largest

### Complexity
- Time: O(n^2) — n iterations, O(n) to find max and flip
- Space: O(1) in-place (O(n) for flip list output)
- At most 2(n-1) flips

---

## 13. Insertion Sort on Linked List (LC 147)

### Signal
- Sort a linked list with insertion sort
- O(1) extra space (no array conversion)
- Good for nearly-sorted linked lists

### Template

```java
public ListNode insertionSortList(ListNode head) {
    ListNode dummy = new ListNode(0); // sorted list head

    ListNode curr = head;
    while (curr != null) {
        ListNode next = curr.next; // save next before detaching

        // Find insertion point in sorted list
        ListNode prev = dummy;
        while (prev.next != null && prev.next.val < curr.val) {
            prev = prev.next;
        }

        // Insert curr after prev
        curr.next = prev.next;
        prev.next = curr;

        curr = next;
    }
    return dummy.next;
}
```

### Optimization: Track tail to avoid full scan when already in order

```java
public ListNode insertionSortListOptimized(ListNode head) {
    ListNode dummy = new ListNode(0);
    ListNode curr = head;
    ListNode lastSorted = dummy; // optimization: track last sorted node

    while (curr != null) {
        ListNode next = curr.next;

        // If current >= last sorted, just append (common for nearly sorted)
        if (lastSorted != dummy && lastSorted.val <= curr.val) {
            lastSorted.next = curr;
            curr.next = null;
            lastSorted = curr;
        } else {
            // Find correct position from beginning
            ListNode prev = dummy;
            while (prev.next != null && prev.next.val < curr.val) {
                prev = prev.next;
            }
            curr.next = prev.next;
            prev.next = curr;
            if (curr.next == null) lastSorted = curr;
        }
        curr = next;
    }
    return dummy.next;
}
```

### Complexity
- Time: O(n^2) worst/average, O(n) if nearly sorted
- Space: O(1)
- Stable: Yes (use `<` not `<=` in comparison for insertion point)

---

## Summary: When to Use What

```
┌─────────────────────────────────────────────────────┐
│ SORTING ALGORITHM SELECTION GUIDE                   │
├─────────────────────────────────────────────────────┤
│                                                     │
│ General purpose?                                    │
│   → Java Arrays.sort() (Tim Sort for objects,       │
│     Dual-Pivot QS for primitives)                   │
│                                                     │
│ Need guaranteed O(n log n) + stable?                │
│   → Merge Sort                                      │
│                                                     │
│ Need guaranteed O(n log n) + in-place?              │
│   → Heap Sort                                       │
│                                                     │
│ Small integers (range k ≈ n)?                       │
│   → Counting Sort                                   │
│                                                     │
│ Large integers, fixed # digits?                     │
│   → Radix Sort                                      │
│                                                     │
│ Floats in [0,1), uniform distribution?              │
│   → Bucket Sort                                     │
│                                                     │
│ Only need kth element?                              │
│   → Quick Select                                    │
│                                                     │
│ 3 distinct values or partition into 3 groups?       │
│   → Dutch National Flag                             │
│                                                     │
│ Linked list?                                        │
│   → Merge Sort (top-down or bottom-up)              │
│                                                     │
│ Nearly sorted?                                      │
│   → Insertion Sort / Tim Sort                       │
│                                                     │
└─────────────────────────────────────────────────────┘
```
