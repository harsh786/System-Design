# Randomized Algorithms, Sampling, and Probability

## Decision Flowchart

```
Need randomness in algorithm?
├── Shuffling/permutation → Fisher-Yates Shuffle
├── Streaming data (unknown size) → Reservoir Sampling
│   ├── Single element → R(1)
│   └── k elements → R(k)
├── Uniform random in complex domain → Rejection Sampling
├── Weighted random selection → Prefix Sum + Binary Search
├── Avoid worst-case deterministic → Randomized pivot
│   ├── Selection (kth element) → Randomized Quick Select
│   └── Sorting → Randomized Quick Sort
├── Probabilistic data structure
│   ├── Membership testing → Bloom Filter
│   └── Ordered operations → Skip List
└── Monte Carlo (may be wrong) vs Las Vegas (always correct, random runtime)
```

## Java Random Utilities

```java
import java.util.Random;
import java.util.concurrent.ThreadLocalRandom;

// Basic usage
Random rand = new Random();
int val = rand.nextInt(n);          // [0, n)
int range = rand.nextInt(b - a) + a; // [a, b)
double d = rand.nextDouble();       // [0.0, 1.0)

// Thread-safe, no contention (preferred in concurrent code)
int val2 = ThreadLocalRandom.current().nextInt(a, b); // [a, b)

// Seeded for reproducibility
Random seeded = new Random(42L);
```

---

## 1. Fisher-Yates Shuffle

**Signal**: Generate a uniform random permutation; "shuffle an array" with equal probability for all orderings.

**Template**:
```java
class Solution {
    private int[] original;
    private Random rand = new Random();

    public Solution(int[] nums) {
        this.original = nums.clone();
    }

    public int[] shuffle() {
        int[] arr = original.clone();
        for (int i = arr.length - 1; i > 0; i--) {
            int j = rand.nextInt(i + 1); // [0, i]
            int tmp = arr[i];
            arr[i] = arr[j];
            arr[j] = tmp;
        }
        return arr;
    }

    public int[] reset() {
        return original.clone();
    }
}
```

**Key Insight**: At each step i (from n-1 down to 0), pick uniformly from remaining positions [0, i]. This produces each of the n! permutations with equal probability 1/n!. The proof is inductive: P(element lands at position i) = 1/n for all i.

**Complexity**: O(n) time, O(n) space.

**Variants**:
- Inside-out version (generate shuffled copy without modifying original)
- Partial shuffle (only need first k elements of a permutation) — stop after k iterations → O(k)
- Sattolo's algorithm (generate random cyclic permutation — use `rand.nextInt(i)` instead of `rand.nextInt(i+1)`)

---

## 2. Reservoir Sampling

**Signal**: Pick k random elements from a stream of unknown/huge size with uniform probability; single pass, O(k) memory.

**Template (k=1)**:
```java
class Solution {
    private ListNode head;
    private Random rand = new Random();

    public Solution(ListNode head) {
        this.head = head;
    }

    public int getRandom() {
        ListNode curr = head;
        int result = curr.val;
        int count = 1;
        while (curr != null) {
            if (rand.nextInt(count) == 0) { // probability 1/count
                result = curr.val;
            }
            count++;
            curr = curr.next;
        }
        return result;
    }
}
```

**Template (k samples — Algorithm R)**:
```java
public int[] reservoirSample(Iterator<Integer> stream, int k) {
    int[] reservoir = new int[k];
    int i = 0;

    // Fill reservoir with first k elements
    while (i < k && stream.hasNext()) {
        reservoir[i++] = stream.next();
    }

    // Replace elements with decreasing probability
    while (stream.hasNext()) {
        int val = stream.next();
        int j = rand.nextInt(i + 1); // [0, i]
        if (j < k) {
            reservoir[j] = val;
        }
        i++;
    }
    return reservoir;
}
```

**Probability Proof (k=1, n elements)**:
- Element at position i is chosen if: selected at step i (prob = 1/i) AND not replaced at any subsequent step.
- P = (1/i) * (i/(i+1)) * ((i+1)/(i+2)) * ... * ((n-1)/n) = 1/n (telescoping)
- Each element has exactly probability 1/n. QED.

**For k samples**: P(element i in reservoir) = k/n. Proof generalizes via conditional probabilities.

**Complexity**: O(n) time, O(k) space — single pass, no need to know n in advance.

**Variants**:
- Weighted reservoir sampling (Algorithm A-Res by Efraimidis-Spirakis)
- Distributed reservoir sampling across multiple machines
- LC 382: Linked List Random Node
- LC 398: Random Pick Index (reservoir for duplicates)

---

## 3. Rejection Sampling

**Signal**: Generate uniform random points in an irregular region; implement one random generator from another.

**Template: Random Point in Circle**:
```java
class Solution {
    private double radius, x_center, y_center;
    private Random rand = new Random();

    public Solution(double radius, double x_center, double y_center) {
        this.radius = radius;
        this.x_center = x_center;
        this.y_center = y_center;
    }

    public double[] randPoint() {
        while (true) {
            // Sample from bounding square [-r, r] x [-r, r]
            double x = rand.nextDouble() * 2 * radius - radius;
            double y = rand.nextDouble() * 2 * radius - radius;
            if (x * x + y * y <= radius * radius) { // accept if in circle
                return new double[]{x_center + x, y_center + y};
            }
            // Reject and retry — acceptance rate = pi/4 ≈ 78.5%
        }
    }
}
```

**Template: Rand7 from Rand10 (LC 470 variant)**:
```java
// Implement rand7() using rand10()
public int rand7() {
    while (true) {
        int val = rand10(); // [1, 10]
        if (val <= 7) return val; // accept
        // reject 8,9,10 — acceptance rate = 70%
    }
}

// Implement rand10() using rand7() — more interesting
public int rand10() {
    while (true) {
        int row = rand7(); // [1,7]
        int col = rand7(); // [1,7]
        int idx = (row - 1) * 7 + col; // [1, 49] uniform
        if (idx <= 40) return (idx - 1) % 10 + 1; // accept — rate = 40/49 ≈ 81.6%
    }
}
```

**Key Insight**: Sample from a larger, easy-to-sample space. Accept if the sample falls in the target region; reject and retry otherwise. Expected attempts = 1 / acceptance_probability.

**Complexity**: Expected O(1/p) per sample where p = acceptance probability. Always terminates (Las Vegas).

---

## 4. Random Pick with Weight

**Signal**: Pick index i with probability proportional to weight[i]; weighted random selection.

**Template**:
```java
class Solution {
    private int[] prefixSum;
    private Random rand = new Random();

    public Solution(int[] w) {
        prefixSum = new int[w.length];
        prefixSum[0] = w[0];
        for (int i = 1; i < w.length; i++) {
            prefixSum[i] = prefixSum[i - 1] + w[i];
        }
    }

    public int pickIndex() {
        int target = rand.nextInt(prefixSum[prefixSum.length - 1]) + 1; // [1, totalWeight]
        // Binary search for leftmost index where prefixSum[i] >= target
        int lo = 0, hi = prefixSum.length - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (prefixSum[mid] < target) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }
}
```

**Key Insight**: Build prefix sums creating "ranges" on a number line. Each index owns a segment proportional to its weight. A uniform random number in [1, total] maps to exactly one index via binary search.

**Complexity**: O(n) build, O(log n) per pick.

---

## 5. Random Pick Index (Reservoir for Duplicates)

**Signal**: Given array with duplicates, pick random index of a target value with equal probability.

**Template**:
```java
class Solution {
    private int[] nums;
    private Random rand = new Random();

    public Solution(int[] nums) {
        this.nums = nums;
    }

    public int pick(int target) {
        int result = -1, count = 0;
        for (int i = 0; i < nums.length; i++) {
            if (nums[i] == target) {
                count++;
                if (rand.nextInt(count) == 0) {
                    result = i;
                }
            }
        }
        return result;
    }
}
```

**Key Insight**: Reservoir sampling with k=1 applied only to indices matching target. No HashMap needed — O(1) space (excluding input), O(n) per call. Trade-off: if picks are frequent, HashMap<Integer, List<Integer>> gives O(1) pick but O(n) space.

---

## 6. Randomized Quick Select

**Signal**: Find kth smallest/largest element in expected O(n) without full sort.

**Template**:
```java
public int findKthLargest(int[] nums, int k) {
    int target = nums.length - k; // convert to kth smallest (0-indexed)
    return quickSelect(nums, 0, nums.length - 1, target);
}

private Random rand = new Random();

private int quickSelect(int[] nums, int lo, int hi, int k) {
    if (lo == hi) return nums[lo];

    // Random pivot to avoid O(n^2) worst case
    int pivotIdx = lo + rand.nextInt(hi - lo + 1);
    swap(nums, pivotIdx, hi);

    int pivot = nums[hi];
    int storeIdx = lo;
    for (int i = lo; i < hi; i++) {
        if (nums[i] < pivot) {
            swap(nums, i, storeIdx++);
        }
    }
    swap(nums, storeIdx, hi);

    if (storeIdx == k) return nums[storeIdx];
    else if (storeIdx < k) return quickSelect(nums, storeIdx + 1, hi, k);
    else return quickSelect(nums, lo, storeIdx - 1, k);
}

private void swap(int[] a, int i, int j) {
    int tmp = a[i]; a[i] = a[j]; a[j] = tmp;
}
```

**Key Insight**: Random pivot ensures expected partition ratio is balanced. Expected recurrence: T(n) = T(n/2) + O(n) → O(n). Worst case remains O(n^2) but probability decreases exponentially with n.

**Complexity**:
- Expected: O(n)
- Worst case: O(n^2) — probability < 1/2^n for adversarial input with random pivot
- Space: O(log n) expected stack depth

**Variants**:
- Median of medians for guaranteed O(n) worst case (deterministic, larger constant)
- Introselect (randomized + fallback to median-of-medians)
- 3-way partition for arrays with many duplicates

---

## 7. Randomized Quick Sort

**Signal**: Sort with O(n log n) expected time, avoiding sorted-input worst case.

**Template**:
```java
public void quickSort(int[] nums, int lo, int hi) {
    if (lo >= hi) return;

    // Random pivot
    int pivotIdx = lo + rand.nextInt(hi - lo + 1);
    swap(nums, pivotIdx, hi);

    // 3-way partition (Dutch National Flag) for duplicate handling
    int lt = lo, gt = hi, i = lo;
    int pivot = nums[hi];
    while (i <= gt) {
        if (nums[i] < pivot) swap(nums, i++, lt++);
        else if (nums[i] > pivot) swap(nums, i, gt--);
        else i++;
    }
    // nums[lo..lt-1] < pivot, nums[lt..gt] == pivot, nums[gt+1..hi] > pivot

    quickSort(nums, lo, lt - 1);
    quickSort(nums, gt + 1, hi);
}
```

**Key Insight**: Random pivot makes the expected number of comparisons 2n ln n ≈ 1.39n log2 n regardless of input distribution. 3-way partition handles duplicates in O(n) for arrays with few distinct values.

**Complexity**: O(n log n) expected, O(n^2) worst case (astronomically unlikely with random pivot).

---

## 8. Monte Carlo vs Las Vegas Algorithms

| Property | Monte Carlo | Las Vegas |
|----------|-------------|-----------|
| Correctness | May be wrong (bounded error) | Always correct |
| Runtime | Deterministic/bounded | Random (expected bound) |
| Example | Randomized primality test (Miller-Rabin) | Randomized Quick Sort |
| Error control | Repeat k times → error ≤ (1/2)^k | N/A — always correct |
| System Design use | Bloom filter, Count-Min Sketch, HyperLogLog | Randomized load balancing |

**Key Concepts**:
```
Monte Carlo: "fast, probably right"
  - One-sided error: if says YES, might be wrong; if says NO, definitely correct
  - Amplification: run k times, take majority vote → error probability exponentially small

Las Vegas: "always right, probably fast"
  - Randomized QuickSort, QuickSelect, Skip List operations
  - Expected O(f(n)), worst case unbounded but probability of bad case → 0
```

---

## 9. Bloom Filter (System Design)

**Signal**: Approximate set membership; "is this element possibly in the set?" with no false negatives.

**Conceptual Template**:
```java
class BloomFilter {
    private BitSet bits;
    private int size;
    private int numHashFunctions;

    public BloomFilter(int expectedElements, double falsePositiveRate) {
        // Optimal sizing: m = -n*ln(p) / (ln2)^2
        this.size = (int) (-expectedElements * Math.log(falsePositiveRate) / (Math.log(2) * Math.log(2)));
        // Optimal hash count: k = (m/n) * ln2
        this.numHashFunctions = (int) ((size / (double) expectedElements) * Math.log(2));
        this.bits = new BitSet(size);
    }

    public void add(String item) {
        for (int i = 0; i < numHashFunctions; i++) {
            int hash = hash(item, i);
            bits.set(Math.floorMod(hash, size));
        }
    }

    public boolean mightContain(String item) {
        for (int i = 0; i < numHashFunctions; i++) {
            int hash = hash(item, i);
            if (!bits.get(Math.floorMod(hash, size))) return false; // definitely not in set
        }
        return true; // possibly in set (false positive possible)
    }

    // Double hashing technique: h_i(x) = h1(x) + i*h2(x)
    private int hash(String item, int i) {
        int h1 = item.hashCode();
        int h2 = Integer.reverse(h1);
        return h1 + i * h2;
    }
}
```

**Key Properties**:
- No false negatives: if `mightContain` returns false, element is definitely absent
- False positives: if returns true, element is probably present (FPR configurable)
- No deletion (use Counting Bloom Filter for deletion support)
- Space: ~10 bits/element for 1% FPR

**System Design Applications**: Cache filtering (avoid unnecessary DB lookups), spam detection, URL deduplication in web crawlers, distributed systems (check if data exists on a node before network call).

---

## 10. Skip List

**Signal**: Randomized alternative to balanced BST; O(log n) expected search/insert/delete with simpler implementation.

**Template**:
```java
class SkipList {
    private static final int MAX_LEVEL = 16;
    private static final double P = 0.5;
    private Node head = new Node(-1, MAX_LEVEL);
    private int level = 0;
    private Random rand = new Random();

    static class Node {
        int val;
        Node[] next;
        Node(int val, int level) {
            this.val = val;
            this.next = new Node[level + 1];
        }
    }

    private int randomLevel() {
        int lvl = 0;
        while (lvl < MAX_LEVEL && rand.nextDouble() < P) lvl++;
        return lvl;
    }

    public boolean search(int target) {
        Node curr = head;
        for (int i = level; i >= 0; i--) {
            while (curr.next[i] != null && curr.next[i].val < target) {
                curr = curr.next[i];
            }
        }
        curr = curr.next[0];
        return curr != null && curr.val == target;
    }

    public void add(int num) {
        Node[] update = new Node[MAX_LEVEL + 1];
        Node curr = head;
        for (int i = level; i >= 0; i--) {
            while (curr.next[i] != null && curr.next[i].val < num) {
                curr = curr.next[i];
            }
            update[i] = curr;
        }

        int newLevel = randomLevel();
        if (newLevel > level) {
            for (int i = level + 1; i <= newLevel; i++) update[i] = head;
            level = newLevel;
        }

        Node newNode = new Node(num, newLevel);
        for (int i = 0; i <= newLevel; i++) {
            newNode.next[i] = update[i].next[i];
            update[i].next[i] = newNode;
        }
    }

    public boolean erase(int num) {
        Node[] update = new Node[MAX_LEVEL + 1];
        Node curr = head;
        for (int i = level; i >= 0; i--) {
            while (curr.next[i] != null && curr.next[i].val < num) {
                curr = curr.next[i];
            }
            update[i] = curr;
        }
        curr = curr.next[0];
        if (curr == null || curr.val != num) return false;

        for (int i = 0; i <= level; i++) {
            if (update[i].next[i] != curr) break;
            update[i].next[i] = curr.next[i];
        }
        while (level > 0 && head.next[level] == null) level--;
        return true;
    }
}
```

**Key Insight**: Each node is promoted to higher levels with probability p (typically 0.5). Expected number of levels = O(log n). Search traverses expected O(log n) nodes by skipping over large sections at higher levels. Used in Redis sorted sets and LevelDB/RocksDB memtables.

**Complexity**: O(log n) expected for search/insert/delete. O(n) space expected.

---

## 11. Linked List Random Node

**Signal**: LC 382 — return a random node's value from a linked list with equal probability.

**Template**: (Same as Reservoir Sampling k=1 — see Pattern 2)

```java
class Solution {
    private ListNode head;
    private Random rand = new Random();

    public Solution(ListNode head) { this.head = head; }

    public int getRandom() {
        ListNode curr = head;
        int result = curr.val, count = 1;
        curr = curr.next;
        while (curr != null) {
            count++;
            if (rand.nextInt(count) == 0) result = curr.val;
            curr = curr.next;
        }
        return result;
    }
}
```

**When to use over alternatives**:
- List changes frequently (no precomputation)
- Memory constrained (can't copy to array)
- If list is static and picks are frequent, copy to array for O(1) picks

---

## 12. Random Point in Non-overlapping Rectangles

**Signal**: LC 497 — pick a random integer point uniformly across multiple rectangles, weighted by area.

**Template**:
```java
class Solution {
    private int[][] rects;
    private int[] prefixAreas;
    private Random rand = new Random();

    public Solution(int[][] rects) {
        this.rects = rects;
        prefixAreas = new int[rects.length];
        prefixAreas[0] = area(rects[0]);
        for (int i = 1; i < rects.length; i++) {
            prefixAreas[i] = prefixAreas[i - 1] + area(rects[i]);
        }
    }

    // Number of integer points in rectangle
    private int area(int[] r) {
        return (r[2] - r[0] + 1) * (r[3] - r[1] + 1);
    }

    public int[] pick() {
        int target = rand.nextInt(prefixAreas[prefixAreas.length - 1]) + 1;

        // Binary search for rectangle
        int lo = 0, hi = prefixAreas.length - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (prefixAreas[mid] < target) lo = mid + 1;
            else hi = mid;
        }

        // Random point within chosen rectangle
        int[] r = rects[lo];
        int x = r[0] + rand.nextInt(r[2] - r[0] + 1);
        int y = r[1] + rand.nextInt(r[3] - r[1] + 1);
        return new int[]{x, y};
    }
}
```

**Key Insight**: Two-level sampling — first pick a rectangle with probability proportional to its number of integer points (weighted random via prefix sum), then pick a uniform random point within that rectangle.

**Complexity**: O(n) build, O(log n) per pick.

---

## Expected vs Worst-Case Complexity Summary

| Algorithm | Expected | Worst Case | Probability of Worst Case |
|-----------|----------|------------|--------------------------|
| Randomized Quick Select | O(n) | O(n^2) | Exponentially small |
| Randomized Quick Sort | O(n log n) | O(n^2) | ~1/n! |
| Skip List search | O(log n) | O(n) | Exponentially small |
| Rejection Sampling (circle) | O(1) per point | Unbounded | Geometric decay |
| Reservoir Sampling | O(n) | O(n) | Deterministic runtime |
| Fisher-Yates | O(n) | O(n) | Deterministic runtime |

**Key distinction**: Reservoir Sampling and Fisher-Yates have deterministic runtime — only their output is random. Quick Select/Sort have random runtime — they always produce the correct answer (Las Vegas).

---

## Common Pitfalls

1. **Off-by-one in Fisher-Yates**: `rand.nextInt(i+1)` not `rand.nextInt(i)` — the latter produces only cyclic permutations (Sattolo's)
2. **Modulo bias**: `rand.nextInt(n)` is correct; `Math.abs(rand.nextInt()) % n` has slight bias for non-power-of-2 n
3. **Seeding in contests**: Use `new Random()` (time-seeded) for submissions, not fixed seed
4. **Reservoir off-by-one**: Count starts at 1 for the first element, not 0
5. **Weighted random**: Target should be in [1, totalWeight] not [0, totalWeight-1] when using prefix sums that start at w[0]

---

## LeetCode Problem Map

| Pattern | Problems |
|---------|----------|
| Fisher-Yates | 384 |
| Reservoir Sampling | 382, 398 |
| Rejection Sampling | 478 (Circle), 470 (Rand10) |
| Weighted Random | 528 |
| Random in Rectangles | 497 |
| Quick Select | 215, 973, 347 |
| Skip List | 1206 |
