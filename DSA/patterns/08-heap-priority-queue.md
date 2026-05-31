# 08 - Heap / Priority Queue Patterns

## Decision Flowchart

```
START: What does the problem ask?
│
├─ "Top K" / "Kth largest/smallest" ──────────────────────► Pattern 1: Top-K
│   └─ Need exact Kth? ──► QuickSelect O(n) avg
│
├─ "Merge K sorted ___" / "Smallest range from K lists" ──► Pattern 2: K-Way Merge
│
├─ "Running median" / "Balance two halves" ────────────────► Pattern 3: Two Heaps
│
├─ "Minimum rooms/servers" / "Cooldown scheduling" ────────► Pattern 4: Scheduling
│
├─ "Rearrange so no adjacent same" ───────────────────────► Pattern 5: Reorganize
│
├─ "Dynamic stream + removals" ────────────────────────────► Pattern 6: Lazy Deletion
│
├─ "Top K frequent" ──────────────────────────────────────► Pattern 7: Freq + Heap
│
├─ "Sliding window + median/order stats" ─────────────────► Pattern 8: Sliding Window Median
│
└─ "Maximize profit given capital constraints" ────────────► Pattern 9: IPO / Greedy Selection
```

### Heap Selection Guide

| Condition | Heap Type |
|-----------|-----------|
| Need smallest K → keep largest candidates | **Max-heap** of size K (pop when > K) |
| Need largest K → keep smallest candidates | **Min-heap** of size K (pop when > K) |
| Process in min-first order | **Min-heap** (natural PQ) |
| Process in max-first order | **Max-heap** (`Collections.reverseOrder()`) |

---

## Pattern 1: Top-K / Kth Largest Element

### Signal
- "Find K largest/smallest elements"
- "Kth largest element in stream/array"
- "K closest points to origin"

### Template (Java)

```java
// Approach A: Min-Heap of size K (for K largest)
// Time: O(N log K) | Space: O(K)
public int findKthLargest(int[] nums, int k) {
    PriorityQueue<Integer> minHeap = new PriorityQueue<>(); // size K
    for (int num : nums) {
        minHeap.offer(num);
        if (minHeap.size() > k) {
            minHeap.poll(); // evict smallest → only K largest remain
        }
    }
    return minHeap.peek(); // Kth largest = smallest among top K
}

// Approach B: QuickSelect (Lomuto partition)
// Time: O(N) avg, O(N^2) worst | Space: O(1)
public int findKthLargestQS(int[] nums, int k) {
    int target = nums.length - k; // convert to index in sorted order
    return quickSelect(nums, 0, nums.length - 1, target);
}

private int quickSelect(int[] nums, int lo, int hi, int target) {
    if (lo == hi) return nums[lo];
    
    // Randomized pivot to avoid worst case
    int pivotIdx = lo + ThreadLocalRandom.current().nextInt(hi - lo + 1);
    swap(nums, pivotIdx, hi);
    
    int pivot = nums[hi], store = lo;
    for (int i = lo; i < hi; i++) {
        if (nums[i] < pivot) {
            swap(nums, store++, i);
        }
    }
    swap(nums, store, hi);
    
    if (store == target) return nums[store];
    else if (store < target) return quickSelect(nums, store + 1, hi, target);
    else return quickSelect(nums, lo, store - 1, target);
}
```

### Visualization

```
Array: [3, 1, 5, 12, 2, 11], K = 3  →  Find 3rd largest

Min-heap (size K=3):

Process 3:   heap = [3]
Process 1:   heap = [1, 3]
Process 5:   heap = [1, 3, 5]
Process 12:  heap = [1, 3, 5, 12] → size>K → poll 1 → [3, 5, 12]
Process 2:   heap = [2, 3, 5, 12] → size>K → poll 2 → [3, 5, 12]
Process 11:  heap = [3, 5, 11, 12] → size>K → poll 3 → [5, 11, 12]

Answer: heap.peek() = 5  ✓ (3rd largest)
```

### Variants
| Problem | Twist |
|---------|-------|
| K Closest Points | Custom comparator on distance |
| Kth Largest in Stream | Maintain heap across `add()` calls |
| K Largest in BST | Reverse inorder (no heap needed) |
| Top K from N sorted files | Combine with K-Way Merge |

### Complexity
| Approach | Time | Space | When to Use |
|----------|------|-------|-------------|
| Min-heap size K | O(N log K) | O(K) | Streaming, K << N |
| QuickSelect | O(N) avg | O(1) | Single query, in-memory |
| Full sort | O(N log N) | O(1) | Need all sorted anyway |
| Bucket sort | O(N) | O(N) | Bounded value range |

---

## Pattern 2: K-Way Merge

### Signal
- "Merge K sorted lists/arrays"
- "Smallest range covering elements from K lists"
- "Kth smallest in sorted matrix"

### Template (Java)

```java
// Merge K Sorted Lists
// Time: O(N log K) where N = total elements | Space: O(K)
public ListNode mergeKLists(ListNode[] lists) {
    PriorityQueue<ListNode> pq = new PriorityQueue<>(
        (a, b) -> a.val - b.val
    );
    
    // Seed: one element from each list
    for (ListNode head : lists) {
        if (head != null) pq.offer(head);
    }
    
    ListNode dummy = new ListNode(0), tail = dummy;
    while (!pq.isEmpty()) {
        ListNode min = pq.poll();
        tail.next = min;
        tail = tail.next;
        if (min.next != null) {
            pq.offer(min.next); // advance that list's pointer
        }
    }
    return dummy.next;
}

// Smallest Range Covering K Lists
// Time: O(N log K) | Space: O(K)
public int[] smallestRange(List<List<Integer>> nums) {
    // Min-heap: [value, listIndex, elementIndex]
    PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[0] - b[0]);
    int curMax = Integer.MIN_VALUE;
    
    for (int i = 0; i < nums.size(); i++) {
        int val = nums.get(i).get(0);
        pq.offer(new int[]{val, i, 0});
        curMax = Math.max(curMax, val);
    }
    
    int[] result = {pq.peek()[0], curMax}; // [rangeStart, rangeEnd]
    
    while (true) {
        int[] min = pq.poll();
        int list = min[1], idx = min[2];
        
        if (idx + 1 == nums.get(list).size()) break; // a list exhausted
        
        int nextVal = nums.get(list).get(idx + 1);
        pq.offer(new int[]{nextVal, list, idx + 1});
        curMax = Math.max(curMax, nextVal);
        
        if (curMax - pq.peek()[0] < result[1] - result[0]) {
            result[0] = pq.peek()[0];
            result[1] = curMax;
        }
    }
    return result;
}
```

### Visualization

```
K-Way Merge (K=3 sorted lists):

List 0: [1, 4, 7]
List 1: [2, 5, 8]
List 2: [3, 6, 9]

Heap state (min-heap):
Step 1: heap = [(1,L0), (2,L1), (3,L2)] → extract 1, push 4 from L0
Step 2: heap = [(2,L1), (4,L0), (3,L2)] → extract 2, push 5 from L1
Step 3: heap = [(3,L2), (4,L0), (5,L1)] → extract 3, push 6 from L2
...
Output: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9

Key insight: Heap always holds exactly K elements (one per list)
```

### Variants
| Problem | Key Difference |
|---------|---------------|
| Kth Smallest in Sorted Matrix | Treat rows as K sorted lists |
| Ugly Number II | 3 "lists" (×2, ×3, ×5 sequences) |
| Find K Pairs with Smallest Sums | Lazy expansion from (0,0) |
| Merge K Sorted Arrays | Same as lists, use index tracking |

### Complexity
- Time: O(N log K) — each of N elements does one heap push/pop
- Space: O(K) — heap never exceeds K entries
- Comparison: Naive pairwise merge = O(NK), divide-and-conquer = O(N log K) same

---

## Pattern 3: Two Heaps — Running Median

### Signal
- "Find median from data stream"
- "Balance two halves dynamically"
- "Sliding window median"

### Template (Java)

```java
class MedianFinder {
    // INVARIANTS:
    // 1. maxHeap.size() >= minHeap.size()  (left half ≥ right half)
    // 2. maxHeap.size() - minHeap.size() <= 1
    // 3. Every element in maxHeap <= every element in minHeap
    
    PriorityQueue<Integer> left;  // max-heap (lower half)
    PriorityQueue<Integer> right; // min-heap (upper half)
    
    public MedianFinder() {
        left  = new PriorityQueue<>(Collections.reverseOrder()); // max-heap
        right = new PriorityQueue<>();                           // min-heap
    }
    
    // Time: O(log N)
    public void addNum(int num) {
        // Step 1: Always offer to left first
        left.offer(num);
        // Step 2: Balance — push max of left to right (maintains ordering)
        right.offer(left.poll());
        // Step 3: Size balance — right can't be larger
        if (right.size() > left.size()) {
            left.offer(right.poll());
        }
    }
    
    // Time: O(1)
    public double findMedian() {
        if (left.size() > right.size()) {
            return left.peek();
        }
        return (left.peek() + right.peek()) / 2.0;
    }
}
```

### Visualization

```
Stream: 5, 15, 1, 3, 8

Add 5:   left=[5]        right=[]         median=5
Add 15:  left=[5]        right=[15]       median=10.0
Add 1:   left=[5,1]→     
         balance: push 5→right, right=[5,15], left=[1]
         size: right>left → move 5 back
         left=[5,1]      right=[15]       median=5
Add 3:   left=[5,3,1]→ push 5→right → left=[3,1] right=[5,15]
         size ok (2==2)
         left=[3,1]      right=[5,15]     median=(3+5)/2=4.0
Add 8:   left=[3,1]+8=[8,3,1]→ push 8→right → left=[3,1] right=[5,8,15]
         size: right>left → move 5 back
         left=[5,3,1]    right=[8,15]     median=5

              left (max-heap)    |    right (min-heap)
                                 |
             ┌─── 5 (top) ──────┼───── 8 (top) ───┐
             │    3              │       15         │
             │    1              │                  │
             └──────────────────┼──────────────────┘
                 lower half      |     upper half
```

### Variants
| Problem | Modification |
|---------|-------------|
| Sliding Window Median | Add lazy deletion (Pattern 8) |
| Percentile from Stream | Adjust size ratio (e.g., 25th → 1:3) |
| Maximize Capital (IPO) | Two heaps: one for filtering, one for selecting |

### Complexity
- `addNum`: O(log N)
- `findMedian`: O(1)
- Space: O(N)

---

## Pattern 4: Scheduling with Heap

### Signal
- "Minimum meeting rooms / servers / CPUs"
- "Task scheduling with cooldown"
- "Interval partitioning / assignment"

### Template (Java)

```java
// Meeting Rooms II — Minimum rooms required
// Time: O(N log N) | Space: O(N)
public int minMeetingRooms(int[][] intervals) {
    Arrays.sort(intervals, (a, b) -> a[0] - b[0]); // sort by start
    
    // Min-heap of end times (each entry = one room's current meeting end)
    PriorityQueue<Integer> rooms = new PriorityQueue<>();
    
    for (int[] meeting : intervals) {
        // If earliest-ending room is free, reuse it
        if (!rooms.isEmpty() && rooms.peek() <= meeting[0]) {
            rooms.poll(); // room freed
        }
        rooms.offer(meeting[1]); // assign this meeting to a room
    }
    return rooms.size(); // total rooms needed
}

// Task Scheduler with Cooldown
// Time: O(N) | Space: O(26) = O(1)
public int leastInterval(char[] tasks, int n) {
    int[] freq = new int[26];
    for (char t : tasks) freq[t - 'A']++;
    
    // Max-heap: process most frequent first
    PriorityQueue<Integer> pq = new PriorityQueue<>(Collections.reverseOrder());
    for (int f : freq) if (f > 0) pq.offer(f);
    
    // Cooldown queue: (remainingCount, availableAtTime)
    Queue<int[]> cooldown = new LinkedList<>();
    int time = 0;
    
    while (!pq.isEmpty() || !cooldown.isEmpty()) {
        time++;
        
        if (!pq.isEmpty()) {
            int cnt = pq.poll() - 1; // execute one instance
            if (cnt > 0) {
                cooldown.offer(new int[]{cnt, time + n}); // available after cooldown
            }
        }
        
        // Release tasks whose cooldown expired
        if (!cooldown.isEmpty() && cooldown.peek()[1] == time) {
            pq.offer(cooldown.poll()[0]);
        }
    }
    return time;
}
```

### Visualization

```
Meeting Rooms II:
Meetings (sorted): [0,30] [5,10] [15,20]

Step 1: rooms = [30]           → room 0 hosts [0,30]
Step 2: peek=30 > 5 (no reuse) → rooms = [10, 30]  → new room 1
Step 3: peek=10 ≤ 15 (reuse!)  → poll 10, push 20 → rooms = [20, 30]
Answer: 2 rooms

Task Scheduler: tasks=[A,A,A,B,B,B], n=2

time=1: pq=[3A,3B] → exec A(2 left), cooldown=[(2,3)]   pq=[3B]
time=2: pq=[3B]    → exec B(2 left), cooldown=[(2,3),(2,4)]  pq=[]
time=3: pq=[] idle?  → cooldown (2,3) released → pq=[2A], exec A(1), cd=[(2,4),(1,5)]
time=4: → release (2,4) → pq=[2B], exec B(1), cd=[(1,5),(1,6)]
time=5: → release (1,5) → pq=[1A], exec A(0), cd=[(1,6)]
time=6: → release (1,6) → pq=[1B], exec B(0)
Answer: 6 (no idle slots with optimal interleaving)
```

### Variants
| Problem | Heap Contains |
|---------|--------------|
| Meeting Rooms II | End times of active meetings |
| Car Pooling | (dropoff_location, passengers) |
| Single-Threaded CPU | (processing_time, index) for available tasks |
| Server Assignment | Next-available-time per server |

### Complexity
- Meeting Rooms: O(N log N) sort + O(N log N) heap ops
- Task Scheduler: O(N) total — bounded by task count, heap has ≤ 26 entries

---

## Pattern 5: Reorganize / Rearrange (No Adjacent Same)

### Signal
- "Rearrange string so no two adjacent chars are same"
- "Distant barcodes" (no adjacent same)
- "Rearrange with distance K between same elements"

### Template (Java)

```java
// Reorganize String — no two adjacent same characters
// Time: O(N log 26) = O(N) | Space: O(26)
public String reorganizeString(String s) {
    int[] freq = new int[26];
    for (char c : s.toCharArray()) freq[c - 'a']++;
    
    // Impossibility check: if max freq > (n+1)/2, impossible
    int maxFreq = Arrays.stream(freq).max().getAsInt();
    if (maxFreq > (s.length() + 1) / 2) return "";
    
    // Max-heap of (frequency, char)
    PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> b[0] - a[0]);
    for (int i = 0; i < 26; i++) {
        if (freq[i] > 0) pq.offer(new int[]{freq[i], i});
    }
    
    StringBuilder sb = new StringBuilder();
    while (pq.size() >= 2) {
        // Take top two most frequent
        int[] first = pq.poll();
        int[] second = pq.poll();
        
        sb.append((char)(first[1] + 'a'));
        sb.append((char)(second[1] + 'a'));
        
        // Decrement and re-add if still remaining
        if (--first[0] > 0) pq.offer(first);
        if (--second[0] > 0) pq.offer(second);
    }
    
    // At most one element left (the odd one if length is odd)
    if (!pq.isEmpty()) {
        sb.append((char)(pq.poll()[1] + 'a'));
    }
    return sb.toString();
}

// Rearrange with distance K
// Time: O(N log K) | Space: O(K)
public String rearrangeString(String s, int k) {
    if (k <= 1) return s;
    int[] freq = new int[26];
    for (char c : s.toCharArray()) freq[c - 'a']++;
    
    PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> b[0] - a[0]);
    for (int i = 0; i < 26; i++)
        if (freq[i] > 0) pq.offer(new int[]{freq[i], i});
    
    Queue<int[]> waitQueue = new LinkedList<>(); // cooldown queue
    StringBuilder sb = new StringBuilder();
    
    while (!pq.isEmpty()) {
        int[] cur = pq.poll();
        sb.append((char)(cur[1] + 'a'));
        cur[0]--;
        waitQueue.offer(cur);
        
        if (waitQueue.size() >= k) { // waited K positions
            int[] ready = waitQueue.poll();
            if (ready[0] > 0) pq.offer(ready);
        }
    }
    return sb.length() == s.length() ? sb.toString() : "";
}
```

### Visualization

```
Input: "aab"

freq: a=2, b=1
Max-heap: [(2,'a'), (1,'b')]

Iteration 1: take top 2 → 'a','b' → result="ab"
             a:1 remaining → re-add [(1,'a')]
Iteration 2: size < 2, single left → append 'a' → result="aba"

Output: "aba" ✓

Impossibility: "aaab" → a=3, length=4, (4+1)/2=2, 3>2 → IMPOSSIBLE
```

### Variants
| Problem | Constraint |
|---------|-----------|
| Reorganize String | Distance = 1 (adjacent) |
| Task Scheduler | Distance = n+1 (cooldown) |
| Rearrange String K Distance | General K distance |
| Distant Barcodes | Same as Reorganize (always possible) |

### Complexity
- Time: O(N log A) where A = alphabet size (26 for lowercase)
- Space: O(A)
- Effectively O(N) for fixed alphabets

---

## Pattern 6: Lazy Deletion

### Signal
- "Need to remove arbitrary elements from heap"
- "Delayed processing / invalidation"
- "Heap with updates to previously inserted elements"

### Template (Java)

```java
// Lazy Deletion Pattern — track "deleted" elements, skip on poll
class LazyHeap {
    PriorityQueue<Integer> heap = new PriorityQueue<>();
    Map<Integer, Integer> deleted = new HashMap<>(); // val → count to skip
    int size = 0;
    
    void add(int val) {
        heap.offer(val);
        size++;
    }
    
    void remove(int val) {
        deleted.merge(val, 1, Integer::sum); // mark for lazy removal
        size--;
    }
    
    int peek() {
        prune();
        return heap.peek();
    }
    
    int poll() {
        prune();
        size--;
        return heap.poll();
    }
    
    // Discard top elements that have been lazily deleted
    private void prune() {
        while (!heap.isEmpty()) {
            int top = heap.peek();
            if (deleted.getOrDefault(top, 0) > 0) {
                heap.poll();
                deleted.merge(top, -1, Integer::sum);
                if (deleted.get(top) == 0) deleted.remove(top);
            } else {
                break;
            }
        }
    }
    
    int size() { return size; }
}
```

### Visualization

```
Lazy Deletion in action:

heap = [2, 5, 7, 10]     deleted = {}

remove(5):
  heap = [2, 5, 7, 10]   deleted = {5: 1}   ← no restructure!

peek():
  top = 2, not in deleted → return 2  ✓

poll():
  return 2
  heap = [5, 7, 10]      deleted = {5: 1}

peek():
  top = 5, IS in deleted → prune! pop 5
  heap = [7, 10]          deleted = {}
  top = 7 → return 7  ✓

Cost: Amortized O(log N) per operation (each element pruned at most once)
```

### When to Use
- Sliding window problems where elements leave the window
- Two-heap median with element removals
- Dijkstra-like algorithms (stale distances)
- Any scenario where `O(N)` remove is too expensive

### Complexity
- Each element is inserted once and pruned once: amortized O(log N) per op
- Space: O(N) for deleted map in worst case
- Trade-off: Faster than TreeMap when you only need min/max, not arbitrary access

---

## Pattern 7: Top K Frequent Elements

### Signal
- "K most frequent elements"
- "Sort by frequency"
- "Top K words by count"

### Template (Java)

```java
// Approach A: Heap — O(N log K)
public int[] topKFrequent(int[] nums, int k) {
    Map<Integer, Integer> freq = new HashMap<>();
    for (int n : nums) freq.merge(n, 1, Integer::sum);
    
    // Min-heap of size K (by frequency)
    PriorityQueue<Integer> pq = new PriorityQueue<>(
        (a, b) -> freq.get(a) - freq.get(b)
    );
    
    for (int key : freq.keySet()) {
        pq.offer(key);
        if (pq.size() > k) pq.poll(); // evict least frequent
    }
    
    int[] result = new int[k];
    for (int i = 0; i < k; i++) result[i] = pq.poll();
    return result;
}

// Approach B: Bucket Sort — O(N) 
public int[] topKFrequentBucket(int[] nums, int k) {
    Map<Integer, Integer> freq = new HashMap<>();
    for (int n : nums) freq.merge(n, 1, Integer::sum);
    
    // Bucket: index = frequency, value = list of elements with that freq
    List<Integer>[] buckets = new List[nums.length + 1];
    for (int i = 0; i < buckets.length; i++) buckets[i] = new ArrayList<>();
    
    for (var entry : freq.entrySet()) {
        buckets[entry.getValue()].add(entry.getKey());
    }
    
    // Collect from highest frequency bucket down
    int[] result = new int[k];
    int idx = 0;
    for (int i = buckets.length - 1; i >= 0 && idx < k; i--) {
        for (int val : buckets[i]) {
            result[idx++] = val;
            if (idx == k) break;
        }
    }
    return result;
}
```

### Visualization

```
nums = [1,1,1,2,2,3], k = 2

Step 1 — Frequency count:
  {1:3, 2:2, 3:1}

Step 2a — Heap approach:
  Process 1(freq=3): heap = [1]
  Process 2(freq=2): heap = [2, 1]  (min-heap by freq: 2 on top since freq=2 < freq=3)
  Process 3(freq=1): heap = [3, 1, 2] → size>k → poll 3 → heap = [2, 1]
  Result: [2, 1] = [1, 2] ✓

Step 2b — Bucket sort approach:
  buckets[1] = [3]
  buckets[2] = [2]
  buckets[3] = [1]
  
  Scan from top: buckets[6]..buckets[4] empty
  buckets[3] → take 1 (idx=0)
  buckets[2] → take 2 (idx=1)  → done! k=2
  Result: [1, 2] ✓
```

### Variants
| Problem | Modification |
|---------|-------------|
| Top K Frequent Words | Tie-break alphabetically (custom comparator) |
| Sort Array by Frequency | Full bucket sort |
| K Most Frequent in Subarray | Sliding window + freq map |
| Least Frequent Elements | Min-heap by freq, collect bottom K |

### Complexity
| Approach | Time | Space | Best When |
|----------|------|-------|-----------|
| Heap | O(N log K) | O(N) | K << N |
| Bucket Sort | O(N) | O(N) | Always optimal if space ok |
| QuickSelect on freq | O(N) avg | O(N) | Single query |

---

## Pattern 8: Sliding Window Median

### Signal
- "Median in sliding window"
- "Running order statistics with removals"
- "Balance two halves as window slides"

### Template (Java)

```java
// Sliding Window Median — Two Heaps + Lazy Deletion
// Time: O(N log N) | Space: O(N)
public double[] medianSlidingWindow(int[] nums, int k) {
    // Max-heap (left/lower half) and Min-heap (right/upper half)
    PriorityQueue<Long> left = new PriorityQueue<>(Collections.reverseOrder());
    PriorityQueue<Long> right = new PriorityQueue<>();
    Map<Long, Integer> deleted = new HashMap<>();
    
    double[] result = new double[nums.length - k + 1];
    int balance = 0; // left.effectiveSize - right.effectiveSize
    
    // Initialize first window
    for (int i = 0; i < k; i++) left.offer((long) nums[i]);
    // Move top half to right
    for (int i = 0; i < k / 2; i++) right.offer(left.poll());
    
    result[0] = getMedian(left, right, k);
    
    for (int i = k; i < nums.length; i++) {
        long incoming = nums[i];
        long outgoing = nums[i - k];
        balance = 0;
        
        // Remove outgoing (lazy)
        deleted.merge(outgoing, 1, Integer::sum);
        if (outgoing <= left.peek()) balance--; // lost from left
        else balance++;                          // lost from right
        
        // Add incoming
        if (!left.isEmpty() && incoming <= left.peek()) {
            left.offer(incoming);
            balance++;
        } else {
            right.offer(incoming);
            balance--;
        }
        
        // Rebalance: balance should be 0 (even k) or 1 (odd k, left bigger)
        if (balance > 0) { right.offer(left.poll()); balance -= 2; }
        if (balance < 0) { left.offer(right.poll()); balance += 2; }
        
        // Prune tops
        pruneTop(left, deleted);
        pruneTop(right, deleted);
        
        result[i - k + 1] = getMedian(left, right, k);
    }
    return result;
}

private void pruneTop(PriorityQueue<Long> heap, Map<Long, Integer> deleted) {
    while (!heap.isEmpty() && deleted.getOrDefault(heap.peek(), 0) > 0) {
        deleted.merge(heap.poll(), -1, Integer::sum);
    }
}

private double getMedian(PriorityQueue<Long> left, PriorityQueue<Long> right, int k) {
    if (k % 2 == 1) return left.peek();
    return ((double) left.peek() + right.peek()) / 2.0;
}
```

### Visualization

```
nums = [1, 3, -1, -3, 5, 3, 6, 7], k = 3

Window [1,3,-1]:
  left(max)=[1,-1]? No — after init: left=[1], right=[-1,3]? 
  Actually init: add all to left=[3,1,-1], move k/2=1 to right
  left=[1,-1], right=[3]  → median = left.peek() = 1? 
  Sorted: [-1,1,3] → median = 1 ✓

Window [3,-1,-3]: remove 1, add -3
  outgoing=1 (in left) → balance--
  incoming=-3 ≤ left.peek(1) → left, balance++
  balance=0, ok
  left=[-1,-3], right=[3]... prune: 1 was lazily deleted
  Actually left effectively [-1,-3] after prune of 1 → rebalance needed
  median = -1 ✓

Key: Lazy deletion avoids O(N) remove; prune only touches heap tops
```

### Complexity
- Time: O(N log N) — each element inserted/deleted once from heap
- Space: O(N) — for heaps + deleted map
- Alternative: Use two TreeMaps (balanced BSTs) for O(N log K) with guaranteed bounds
  ```java
  TreeMap<Integer, Integer> left, right; // value → count
  ```

---

## Pattern 9: IPO / Greedy Selection

### Signal
- "Maximize total value given a budget/resource constraint"
- "Select K projects to maximize profit given capital limits"
- "Greedy: among available options, pick the best"

### Template (Java)

```java
// IPO: Maximize Capital — pick at most K projects
// Time: O(N log N) | Space: O(N)
public int findMaximizedCapital(int k, int w, int[] profits, int[] capital) {
    int n = profits.length;
    
    // Pair projects and sort by capital requirement
    int[][] projects = new int[n][2];
    for (int i = 0; i < n; i++) {
        projects[i] = new int[]{capital[i], profits[i]};
    }
    Arrays.sort(projects, (a, b) -> a[0] - b[0]); // sort by capital needed
    
    // Max-heap of profits (available projects)
    PriorityQueue<Integer> available = new PriorityQueue<>(Collections.reverseOrder());
    
    int idx = 0;
    for (int i = 0; i < k; i++) {
        // Unlock all projects affordable with current capital
        while (idx < n && projects[idx][0] <= w) {
            available.offer(projects[idx][1]); // add profit
            idx++;
        }
        
        if (available.isEmpty()) break; // no affordable project
        
        w += available.poll(); // pick most profitable available project
    }
    return w;
}
```

### Visualization

```
k=2, w=0 (initial capital)
profits  = [1, 2, 3]
capital  = [0, 1, 1]

Sorted by capital: [(0,1), (1,2), (1,3)]

Round 1 (w=0):
  Unlock: capital[0]=0 ≤ 0 → available = [1]
  Pick best: profit=1 → w = 0+1 = 1

Round 2 (w=1):
  Unlock: capital[1]=1 ≤ 1 → available = [2]
          capital[2]=1 ≤ 1 → available = [3, 2]
  Pick best: profit=3 → w = 1+3 = 4

Answer: 4

Pattern: Sort by constraint → sweep pointer → max-heap for greedy choice
         ─────────────────   ────────────   ─────────────────────────
         "What's lockable?"  "Unlock as    "Among unlocked, pick
                              budget grows"  the best"
```

### Variants
| Problem | Constraint | Greedy Pick |
|---------|-----------|-------------|
| IPO | Capital needed ≤ current w | Max profit |
| Job Scheduling (Weighted) | Deadline ≤ current time | Max profit job |
| Course Schedule III | Duration ≤ remaining time | Swap longest if beneficial |
| Minimum Cost to Hire K Workers | Quality ratio threshold | Min-cost group |

### General Framework

```java
// Sort items by "unlocking" attribute
// Sweep through, adding items to max-heap as they become available
// Greedily pick the best from heap
Arrays.sort(items, byConstraint);
PriorityQueue<Item> pq = new PriorityQueue<>(byBestValue);
int ptr = 0;

for (each selection round) {
    while (ptr < n && items[ptr].constraint <= currentResource) {
        pq.offer(items[ptr++]);
    }
    if (!pq.isEmpty()) {
        bestChoice = pq.poll();
        updateResource(bestChoice);
    }
}
```

### Complexity
- Time: O(N log N) for sort + O(K log N) for K selections = O(N log N)
- Space: O(N) for heap

---

## Master Comparison Table

| Pattern | Heap Type | Size Bound | Core Idea |
|---------|-----------|-----------|-----------|
| Top-K | Min (for max-K) | K | Evict worst, keep best K |
| K-Way Merge | Min | K | One representative per source |
| Two Heaps | Max + Min | N/2 each | Partition at median |
| Scheduling | Min (end times) | Active | Earliest-free resource |
| Reorganize | Max (frequency) | Alphabet | Greedy most-frequent first |
| Lazy Deletion | Any | N | Defer removal to access time |
| Top K Frequent | Min (by freq) | K | Freq map → heap selection |
| Sliding Median | Max + Min + lazy | Window | Two heaps + lazy deletion |
| IPO / Greedy | Max (value) | Unlocked | Sort constraint, heap value |

## Java PriorityQueue Cheat Sheet

```java
// Min-heap (default)
PriorityQueue<Integer> minHeap = new PriorityQueue<>();

// Max-heap
PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Collections.reverseOrder());

// Custom comparator (e.g., by second element of array)
PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[1] - b[1]);

// CAUTION: a - b overflows for Integer.MIN_VALUE / MAX_VALUE
// Safe: Integer.compare(a, b)

// Key operations:
pq.offer(x);    // O(log N) — add
pq.poll();      // O(log N) — remove min/max
pq.peek();      // O(1)     — view min/max
pq.remove(x);   // O(N)     — avoid! use lazy deletion instead
pq.size();       // O(1)
```

## Anti-Patterns and Pitfalls

| Mistake | Fix |
|---------|-----|
| Using `pq.remove(obj)` in a loop | Use lazy deletion (Pattern 6) |
| `(a, b) -> a - b` with large values | Use `Integer.compare(a, b)` |
| Forgetting heap is NOT sorted | Only top is guaranteed min/max |
| Using heap when TreeMap needed | If you need `floor()`, `ceiling()`, use TreeMap |
| Heap for "Kth largest" when K=N/2 | QuickSelect is O(N) — better |
| Not checking `isEmpty()` before `peek()`/`poll()` | Always guard |
