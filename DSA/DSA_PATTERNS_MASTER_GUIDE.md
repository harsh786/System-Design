# DSA Patterns Master Guide - Staff Architect Interview Preparation

> **Philosophy:** Every problem is an instance of a pattern. Learn the pattern, recognize the signal, apply the template.

---

## TABLE OF CONTENTS

### Part A: Core Data Structures
A1. [Arrays](#a1-arrays)
A2. [Strings](#a2-strings)
A3. [Hash Table](#a3-hash-table)
A4. [Linked List](#a4-linked-list)
A5. [Stack](#a5-stack)
A6. [Queue](#a6-queue)
A7. [Heap / Priority Queue](#a7-heap--priority-queue)
A8. [Trees & BST](#a8-trees--bst)
A9. [Trie](#a9-trie)
A10. [Matrix](#a10-matrix)

### Part B: Algorithmic Patterns
1. [Two Pointers](#1-two-pointers)
2. [Sliding Window](#2-sliding-window)
3. [Binary Search](#3-binary-search)
4. [Dynamic Programming](#4-dynamic-programming)
5. [Greedy](#5-greedy)
6. [Backtracking](#6-backtracking)
7. [Graphs](#7-graphs)
8. [Union-Find](#9-union-find)
9. [Divide and Conquer](#10-divide-and-conquer)
10. [Bit Manipulation](#11-bit-manipulation)
11. [Monotonic Stack](#12-monotonic-stack)
12. [Monotonic Queue](#13-monotonic-queue)
13. [Segment Tree / BIT](#15-segment-tree--bit)
14. [Topological Sort](#16-topological-sort)
15. [Shortest Path Algorithms](#17-shortest-path-algorithms)
16. [Minimum Spanning Tree](#18-minimum-spanning-tree)
17. [String Matching](#19-string-matching)
18. [Game Theory](#20-game-theory)
19. [Design Patterns](#21-design-patterns)
20. [Concurrency Patterns](#22-concurrency-patterns)
21. [Prefix Sum](#24-prefix-sum)
22. [Sweep Line](#25-sweep-line)
23. [Recursion Patterns](#26-recursion-patterns)
24. [Advanced Patterns](#23-advanced-patterns)
25. [Master Cheat Sheet](#master-cheat-sheet)

---

# PART A: CORE DATA STRUCTURES

---

## A1. ARRAYS

### Pattern A1.1: Kadane's Algorithm (Max Subarray Sum)

**Signal:** Find maximum/minimum sum contiguous subarray.

```
maxSum = curSum = nums[0]
for i = 1 to n-1:
    curSum = max(nums[i], curSum + nums[i])   // extend or restart
    maxSum = max(maxSum, curSum)
return maxSum
```

```
Array:  [-2, 1, -3, 4, -1, 2, 1, -5, 4]
curSum:  -2  1  -2  4   3  5  6   1  5
                    ^────────────^
                    max subarray sum = 6

Variant (Max Product): track both maxProd and minProd (negatives flip)
  maxHere = max(num, maxHere * num, minHere * num)
  minHere = min(num, maxHere * num, minHere * num)
```

**Complexity:** O(n) time, O(1) space

### Pattern A1.2: Prefix Sum + HashMap (Subarray Sum = K)

**Signal:** Count subarrays with exact sum K, sum divisible by K, equal 0s and 1s.

```
map = {0: 1}     // empty prefix has sum 0
runningSum = 0, count = 0
for num in nums:
    runningSum += num
    count += map.get(runningSum - k, 0)    // how many prefix sums = runningSum - k?
    map[runningSum] = map.get(runningSum, 0) + 1
```

```
WHY IT WORKS:
  If prefix[j] - prefix[i] = k, then subarray (i, j] sums to k
  We look up how many previous prefix sums equal (current - k)

  nums: [1, 1, 1], k = 2
  prefix: 0, 1, 2, 3
  at prefix=2: check 2-2=0 → exists (1 time) → count=1
  at prefix=3: check 3-2=1 → exists (1 time) → count=2
  Answer: 2 subarrays [1,1]
```

**Complexity:** O(n) time, O(n) space

### Pattern A1.3: Dutch National Flag (3-Way Partition)

**Signal:** Sort array with 3 distinct values in-place, or partition around pivot.

```
lo = 0, mid = 0, hi = n-1
while mid <= hi:
    if arr[mid] == 0: swap(arr, lo, mid); lo++; mid++
    elif arr[mid] == 1: mid++
    else:              swap(arr, mid, hi); hi--

// Invariant: [0..lo-1]=0s | [lo..mid-1]=1s | [mid..hi]=unknown | [hi+1..n-1]=2s
```

```
[2, 0, 1, 2, 0, 1]
 ^lo,mid         ^hi
Step by step → [0, 0, 1, 1, 2, 2]
```

**Complexity:** O(n) time, O(1) space

### Pattern A1.4: Boyer-Moore Voting (Majority Element)

**Signal:** Find element appearing > n/2 times. O(1) space.

```
candidate = null, count = 0
for num in nums:
    if count == 0: candidate = num
    count += (1 if num == candidate else -1)
return candidate

// Intuition: majority element survives all "cancellations"
// For > n/3: keep two candidates with two counts
```

### Pattern A1.5: Cyclic Sort (Missing/Duplicate in [1..n])

**Signal:** Array of length n with values in [1, n], find missing/duplicate.

```
for i in range(n):
    while nums[i] != i + 1 and nums[nums[i] - 1] != nums[i]:
        swap(nums, i, nums[i] - 1)   // put each number in its correct index

// After: nums[i] != i+1 means i+1 is missing, nums[i] is misplaced
```

**Problems:** First Missing Positive, Find All Duplicates, Find Missing Number

### Pattern A1.6: Interval Merge/Overlap

**Signal:** Merge overlapping intervals, insert interval, find conflicts.

```
Sort by start time
merged = [intervals[0]]
for [start, end] in intervals[1:]:
    if start <= merged[-1][1]:          // overlaps
        merged[-1][1] = max(merged[-1][1], end)
    else:
        merged.append([start, end])

// Variant: count max overlapping at any point → sweep line (see Pattern 25)
```

### Pattern A1.7: Rotate Array (Reverse Trick)

```
Rotate right by k:
  k = k % n
  reverse(0, n-1)       // reverse entire
  reverse(0, k-1)       // reverse first k
  reverse(k, n-1)       // reverse rest

[1,2,3,4,5,6,7] k=3 → [7,6,5,4,3,2,1] → [5,6,7,4,3,2,1] → [5,6,7,1,2,3,4]
```

### Pattern A1.8: Two-Pass Left-Right Product

**Signal:** Compute result depending on both left and right context, without division.

```
Product Except Self:
  result[i] = leftProduct[i] * rightProduct[i]
  
  Optimize to O(1) space:
  forward pass: result[i] = running product from left
  backward pass: multiply result[i] by running product from right
```

---

## A2. STRINGS

### Pattern A2.1: Character Frequency Array

**Signal:** Anagram check, character comparisons, frequency constraints.

```
int[] freq = new int[26];
for (char c : s.toCharArray()) freq[c - 'a']++;

// Compare: Arrays.equals(freq1, freq2) for anagram
// Why not HashMap? Array[26] = no hashing overhead, cache-friendly, constant space
```

### Pattern A2.2: Palindrome - Expand from Center

**Signal:** Find longest palindromic substring, count palindromes.

```
for center in 0..n-1:
    // odd length: expand(center, center)
    // even length: expand(center, center+1)

expand(l, r):
    while l >= 0 and r < n and s[l] == s[r]:
        update answer
        l--; r++
```

```
  "babad"
   ^ expand(1,1): "aba" ✓
     ^ expand(2,2): "bab" ✓
  Longest = 3
```

**Complexity:** O(n²) time, O(1) space. For O(n): Manacher's algorithm.

### Pattern A2.3: Encode/Decode Strings

**Signal:** Serialize list of strings to single string (handles any chars).

```
Encode: length + delimiter + string
  ["hello","world"] → "5#hello5#world"

Decode: read number until '#', extract that many chars, repeat
```

### Pattern A2.4: Decode Nested Strings (Stack)

**Signal:** Nested patterns like `3[a2[c]]` → "accaccacc"

```
Stack of (currentString, multiplier):
  digit → build number
  '['  → push (current, num) to stack, reset
  ']'  → pop (prev, num), current = prev + current * num
  char → append to current
```

### Pattern A2.5: String Hashing / Comparison

```
Sorted key:      "eat" → "aet" (for anagram grouping)
Frequency key:   "eat" → "1a1e1t" (O(n) vs O(n log n))
Pattern key:     "egg" → "0.1.1" (for isomorphic/word pattern)
```

### Pattern A2.6: Parentheses Generation

**Signal:** Generate all valid combinations of n pairs.

```
def generate(open, close, current):
    if len(current) == 2*n: result.add(current)
    if open < n: generate(open+1, close, current + "(")
    if close < open: generate(open, close+1, current + ")")

// Key constraint: close < open (never close before opening)
// Count: Catalan number C(n) = (2n)! / ((n+1)! * n!)
```

---

## A3. HASH TABLE

### Pattern A3.1: Complement Lookup (Two Sum)

**Signal:** Find pair with property, one-pass matching.

```
map = {}
for i, num in enumerate(nums):
    complement = target - num
    if complement in map: return [map[complement], i]
    map[num] = i

// Key insight: store what you've SEEN, look up what you NEED
```

### Pattern A3.2: Frequency Counting + Bucket Sort

**Signal:** Top K frequent, sort by frequency.

```
Step 1: Count frequencies → freq = Counter(nums)
Step 2: Bucket sort → bucket[count] = [elements with that frequency]
Step 3: Iterate buckets from high to low → collect K elements

// O(n) time vs O(n log k) with heap
```

### Pattern A3.3: Group by Computed Key

**Signal:** Group items sharing a property.

```
map = defaultdict(list)
for item in items:
    key = computeKey(item)
    map[key].append(item)

Keys:
  Anagrams:    sorted(word) or frequency tuple
  Isomorphic:  pattern encoding "0.1.1"
  Word Pattern: "dog cat cat" → "0.1.1"
```

### Pattern A3.4: Hash as Visited/Cycle Detection

**Signal:** Detect cycle in sequence, happy number.

```
seen = set()
while x not in seen:
    seen.add(x)
    x = transform(x)
// x is the cycle entry point

// Alternative: Floyd's tortoise/hare for O(1) space
```

### Pattern A3.5: Longest Consecutive Sequence

**Signal:** Find longest consecutive sequence in unsorted array. O(n).

```
numSet = set(nums)
maxLen = 0
for num in numSet:
    if num - 1 not in numSet:       // only start from sequence beginning
        length = 1
        while num + length in numSet:
            length++
        maxLen = max(maxLen, length)
```

---

## A4. LINKED LIST

### Pattern A4.1: Fast/Slow Pointer (Floyd's)

**Signal:** Detect cycle, find cycle start, find middle.

```
CYCLE DETECTION:
  slow = fast = head
  while fast and fast.next:
      slow = slow.next
      fast = fast.next.next
      if slow == fast: return true  // cycle!

FIND CYCLE START:
  After meeting, reset slow = head
  while slow != fast:
      slow = slow.next
      fast = fast.next
  return slow  // entry point

FIND MIDDLE:
  slow = fast = head
  while fast and fast.next:
      slow = slow.next
      fast = fast.next.next
  return slow  // middle (left-middle for even length)
```

```
Cycle Detection:
  1 → 2 → 3 → 4 → 5
              ↑         ↓
              └─────────┘
  slow: 1,2,3,4,5,3,4...
  fast: 1,3,5,4,3,5,4...
  Meet at 4 → cycle exists
```

### Pattern A4.2: Reverse Linked List

**Signal:** Reverse whole list, reverse between positions, reverse in k-groups.

```
ITERATIVE (most common):
  prev = null, curr = head
  while curr:
      next = curr.next
      curr.next = prev
      prev = curr
      curr = next
  return prev  // new head

REVERSE BETWEEN [left, right]:
  1. Advance to position left-1 (connection point)
  2. Reverse the sublist from left to right
  3. Reconnect: before.next.next = after, before.next = newHead
```

```
  null ← 1 ← 2 ← 3    prev=3 (new head)
  
  Reverse k-group:
  [1→2→3] → [4→5→6] → [7→8]
  [3→2→1] → [6→5→4] → [7→8]  (last group < k stays)
```

### Pattern A4.3: Merge Sorted Lists

```
MERGE TWO:
  dummy = ListNode(0), tail = dummy
  while l1 and l2:
      if l1.val <= l2.val: tail.next = l1; l1 = l1.next
      else: tail.next = l2; l2 = l2.next
      tail = tail.next
  tail.next = l1 or l2
  return dummy.next

MERGE K (Divide & Conquer or Heap):
  D&C: pair-wise merge, halving count each round → O(N log k)
  Heap: push head of each list, pop min, push its next → O(N log k)
```

### Pattern A4.4: Dummy Head Technique

**Signal:** When head might change (deletion, insertion, partition).

```
dummy = ListNode(0)
dummy.next = head
// operate with prev = dummy
return dummy.next  // real head
```

**Always use dummy when:** removing nodes, partitioning, merging.

### Pattern A4.5: Nth from End (Two Pointers with Gap)

```
fast = head
for i in range(n): fast = fast.next   // advance fast by n
slow = head
while fast.next:
    slow = slow.next
    fast = fast.next
// slow is at (n+1)th from end → slow.next is target
```

### Pattern A4.6: Reorder / Interleave

**Signal:** L0→Ln→L1→Ln-1→... or odd-even split.

```
1. Find middle (fast/slow)
2. Reverse second half
3. Interleave/merge both halves

1→2→3→4→5  →  1→5→2→4→3
```

### Pattern A4.7: Copy List with Random Pointer

```
Approach 1: HashMap (O(n) space)
  map[original] = clone
  Two passes: create nodes, wire next/random

Approach 2: Interleave (O(1) space)
  1→1'→2→2'→3→3'  (insert clone after each original)
  Wire random: clone.random = original.random.next
  Separate lists
```

---

## A5. STACK

### Pattern A5.1: Bracket Matching / Validation

**Signal:** Valid parentheses, matching delimiters, nested structures.

```
map = {')':'(', ']':'[', '}':'{'}
stack = []
for c in s:
    if c in "({[":
        stack.push(c)
    else:
        if not stack or stack[-1] != map[c]: return false
        stack.pop()
return stack.isEmpty()
```

### Pattern A5.2: Monotonic Stack (Next Greater/Smaller)

**Signal:** Next greater element, daily temperatures, stock span, largest rectangle.

```
NEXT GREATER ELEMENT:
  stack = []  // indices, maintaining DECREASING values
  result = [-1] * n
  for i in range(n):
      while stack and nums[i] > nums[stack[-1]]:
          result[stack.pop()] = nums[i]   // found next greater
      stack.push(i)
```

```
nums:   [2, 1, 2, 4, 3]
stack:  [0]           → push 2
        [0,1]         → push 1 (1<2, no pop)
        [2]           → 2≥1 pop→ans[1]=2; 2≥2 pop→ans[0]=2; push
        [3]           → 4>2 pop→ans[2]=4; push 4
        [3,4]         → 3<4, push
result: [2, 2, 4, -1, -1]

VARIANTS:
  Next Smaller: maintain INCREASING stack
  Previous Greater: iterate left to right, check stack top
  Circular: iterate 2*n with i%n
```

### Pattern A5.3: Largest Rectangle in Histogram

**Signal:** Largest rectangular area in histogram bars.

```
stack = [-1]  // sentinel for width calculation
maxArea = 0
for i in range(n + 1):
    h = heights[i] if i < n else 0    // sentinel bar of height 0
    while stack[-1] != -1 and h <= heights[stack[-1]]:
        height = heights[stack.pop()]
        width = i - stack[-1] - 1      // between current and new top
        maxArea = max(maxArea, height * width)
    stack.append(i)

// Extension: Maximal Rectangle in 2D matrix
//   For each row, compute histogram heights, apply this algorithm
```

```
heights: [2, 1, 5, 6, 2, 3]

  6 █
  5 █ █
  3 █ █     █
  2 █ █ █ █ █ █
  1 █ █ █ █ █ █
    ─────────────
    2 1 5 6 2 3
    
  Largest rectangle: 5*2 = 10 (columns 2-3, height 5)
```

### Pattern A5.4: Expression Evaluation (Calculator)

**Signal:** Parse arithmetic with +,-,*,/,() and evaluate.

```
BASIC CALCULATOR II (no parens):
  stack = [], num = 0, op = '+'
  for c in s + '+':             // append dummy operator
      if c.isdigit(): num = num * 10 + int(c)
      elif c is operator:
          if op == '+': stack.push(num)
          elif op == '-': stack.push(-num)
          elif op == '*': stack.push(stack.pop() * num)
          elif op == '/': stack.push(trunc(stack.pop() / num))
          op = c; num = 0
  return sum(stack)

WITH PARENTHESES:
  On '(': push current result and operator, reset
  On ')': pop and combine
  OR use recursion: when '(' → recurse, when ')' → return
```

### Pattern A5.5: Stack for Simulation / Undo

**Signal:** Asteroid collision, backspace compare, undo operations.

```
ASTEROID COLLISION:
  stack = []
  for a in asteroids:
      alive = true
      while alive and stack and a < 0 < stack[-1]:
          if stack[-1] < -a:
              stack.pop()        // top explodes
          elif stack[-1] == -a:
              stack.pop()        // both explode
              alive = false
          else:
              alive = false      // current explodes
      if alive:
          stack.push(a)
```

### Pattern A5.6: Min Stack / Max Stack

**Signal:** O(1) getMin/getMax alongside push/pop.

```
Approach 1: Two stacks
  main stack + minStack (tracks min at each height)
  push(x): push to main; push min(x, minStack.top) to minStack
  pop(): pop both
  getMin(): minStack.top

Approach 2: Single stack storing (value, currentMin) tuples
```

### Pattern A5.7: Remove K Digits (Greedy + Stack)

**Signal:** Build smallest/largest number by removing digits.

```
stack = []
for digit in num:
    while k > 0 and stack and stack[-1] > digit:
        stack.pop(); k--       // remove larger digits
    stack.push(digit)
// remove remaining k from end
// strip leading zeros
```

---

## A6. QUEUE

### Pattern A6.1: BFS Level-Order Processing

**Signal:** Process graph/tree level by level, shortest path in unweighted graph.

```
queue = deque([start])
visited = {start}
level = 0
while queue:
    size = len(queue)              // CRITICAL: snapshot current level size
    for _ in range(size):
        node = queue.popleft()
        process(node)
        for neighbor in adj(node):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    level++
```

### Pattern A6.2: Multi-Source BFS

**Signal:** Propagation from multiple starting points simultaneously.

```
queue = deque()
for source in all_sources:
    queue.append((source, 0))
    visited.add(source)
// BFS as normal — all sources expand simultaneously at same "level"

// Key insight: instead of BFS from each source separately (expensive),
// put ALL sources in queue at start → one BFS handles everything
```

**Problems:** Rotting Oranges, Walls and Gates, 01 Matrix, Surrounded Regions

### Pattern A6.3: Monotonic Deque (Sliding Window Max/Min)

**Signal:** Maximum/minimum in every sliding window of size k.

```
deque = []  // stores INDICES, front = index of maximum in window
result = []
for i in range(n):
    // 1. Remove out-of-window from front
    while deque and deque[0] <= i - k:
        deque.popleft()
    // 2. Remove smaller elements from back (they'll never be max)
    while deque and nums[deque[-1]] <= nums[i]:
        deque.pop()
    // 3. Add current
    deque.append(i)
    // 4. Record answer once window is full
    if i >= k - 1:
        result.append(nums[deque[0]])
```

```
nums: [1, 3, -1, -3, 5, 3, 6, 7], k=3
deque (values): [3] → [3,-1] → [3,-1,-3] → [5] → [5,3] → [6] → [7]
results:                  3       3         5      5      6      7

Invariant: deque always DECREASING (front is max, back is recent smaller)
```

**Complexity:** O(n) time (each element enters/exits deque once), O(k) space

### Pattern A6.4: Circular Queue / Deque

```
class CircularQueue:
    arr[capacity], front = 0, rear = -1, size = 0
    
    enqueue(x): rear = (rear + 1) % capacity; arr[rear] = x; size++
    dequeue():  val = arr[front]; front = (front + 1) % capacity; size--
    isFull():   size == capacity
    isEmpty():  size == 0
```

### Pattern A6.5: Queue with Stack Interconversion

```
QUEUE USING 2 STACKS:
  push: push to inStack
  pop:  if outStack empty → pour inStack into outStack (reverses order)
        pop from outStack
  
  Amortized O(1): each element moves at most twice

STACK USING 2 QUEUES:
  push: enqueue to q2, pour q1 into q2, swap q1/q2
  pop: dequeue from q1
```

### Pattern A6.6: Priority Queue as BFS (0-1 BFS, Dijkstra)

```
0-1 BFS (weights 0 or 1):
  deque instead of priority queue
  weight-0 edge → push to FRONT
  weight-1 edge → push to BACK
  O(V+E) vs Dijkstra's O((V+E)logV)
```

---

## A7. HEAP / PRIORITY QUEUE

### Pattern A7.1: Top-K / Kth Largest

**Signal:** Find K largest/smallest/most frequent.

```
MIN-HEAP OF SIZE K (for Kth largest):
  for num in stream:
      heap.push(num)
      if heap.size > k: heap.pop()   // remove smallest
  return heap.peek()                  // kth largest = smallest in top-k

WHY MIN-HEAP for Kth LARGEST?
  Heap maintains K largest elements
  Smallest of those K = Kth largest
  
  Alternative: MAX-HEAP of size (n-k) → pop (n-k) elements
  Alternative: QuickSelect → O(n) average
```

### Pattern A7.2: Merge K Sorted Lists/Streams

```
heap = MinHeap()
for i, list in enumerate(lists):
    if list: heap.push((list[0].val, i, list[0]))

while heap:
    val, listIdx, node = heap.pop()
    result.append(node)
    if node.next:
        heap.push((node.next.val, listIdx, node.next))

Complexity: O(N log k) where N = total elements, k = number of lists
```

### Pattern A7.3: Two Heaps (Running Median)

**Signal:** Maintain median as elements stream in.

```
maxHeap (left half - smaller elements)
minHeap (right half - larger elements)

addNum(x):
    maxHeap.push(x)
    minHeap.push(maxHeap.pop())        // ensure all left ≤ all right
    if minHeap.size > maxHeap.size:
        maxHeap.push(minHeap.pop())    // keep left ≥ right in size

getMedian():
    if equal sizes: (maxHeap.peek() + minHeap.peek()) / 2
    else: maxHeap.peek()               // left heap has extra element
```

```
Stream: [5, 2, 8, 1, 9]

  Add 5: maxH=[5], minH=[]          median=5
  Add 2: maxH=[2], minH=[5]         median=3.5
  Add 8: maxH=[2,5], minH=[8]       median=5
  Add 1: maxH=[1,2], minH=[5,8]     median=3.5
  Add 9: maxH=[1,2,5], minH=[8,9]   median=5
```

### Pattern A7.4: Greedy Scheduling with Heap

**Signal:** Meeting rooms, task scheduling, CPU scheduling.

```
MEETING ROOMS II (min rooms needed):
  Sort meetings by start time
  Min-heap of end times (tracks when rooms free up)
  for [start, end] in meetings:
      if heap and heap[0] <= start:
          heap.pop()           // reuse freed room
      heap.push(end)
  return heap.size              // max concurrent rooms

TASK SCHEDULER:
  Max-heap of frequencies + cooldown queue
  Each tick: pop max-freq task, decrement, add to cooldown
  When cooldown expires: push back to heap
```

### Pattern A7.5: Lazy Deletion

**Signal:** Need to remove specific elements from heap efficiently.

```
Instead of expensive heap removal:
  Mark element as "deleted" in a HashMap/Set
  On pop: skip any elements that are marked deleted

Usage: Sliding Window Median, dynamic top-K
```

### Pattern A7.6: Reorganize / Rearrange with Heap

**Signal:** Rearrange array so no two adjacent elements are same.

```
Max-heap by frequency
prev = null
while heap not empty:
    curr = heap.pop()                  // most frequent available
    result.append(curr.char)
    curr.freq--
    if prev and prev.freq > 0:
        heap.push(prev)                // push back previous (now eligible)
    prev = curr
```

---

## A8. TREES & BST

### Pattern A8.1: DFS Traversals (Pre/In/Post)

```
PREORDER (Root-L-R):  process BEFORE children → serialize, copy tree
INORDER (L-Root-R):   BST gives SORTED order → kth smallest, validate
POSTORDER (L-R-Root): process AFTER children → delete, height, diameter

ITERATIVE INORDER (most common interview variant):
  stack = [], curr = root
  while curr or stack:
      while curr:
          stack.push(curr)
          curr = curr.left
      curr = stack.pop()
      visit(curr)
      curr = curr.right
```

### Pattern A8.2: Tree DP (Diameter, Max Path Sum)

**Signal:** Optimization where answer at node combines subtree results.

```
TEMPLATE:
  globalAnswer = initial
  
  def dfs(node) → returns value to parent:
      if not node: return base
      left = dfs(node.left)
      right = dfs(node.right)
      
      // Update global: uses BOTH branches (path through this node)
      globalAnswer = max(globalAnswer, combine(left, right, node))
      
      // Return to parent: only SINGLE branch (path up through this node)
      return singleBranch(left, right, node)

DIAMETER:
  globalAnswer = max(globalAnswer, left + right)  // edges through node
  return max(left, right) + 1                      // height

MAX PATH SUM:
  left = max(0, dfs(left))                         // ignore negative paths
  right = max(0, dfs(right))
  globalAnswer = max(globalAnswer, left + right + node.val)
  return max(left, right) + node.val
```

### Pattern A8.3: Level Order BFS + Variants

```
STANDARD:
  queue = [root]
  while queue:
      level = []
      for _ in range(len(queue)):
          node = queue.popleft()
          level.append(node.val)
          if node.left: queue.append(node.left)
          if node.right: queue.append(node.right)
      result.append(level)

VARIANTS:
  Right Side View: take LAST element of each level
  Zigzag: reverse alternate levels
  Average of Levels: compute mean per level
  Largest Value in Each Row: take max per level
```

### Pattern A8.4: LCA (Lowest Common Ancestor)

```
GENERAL BINARY TREE:
  def lca(node, p, q):
      if not node or node == p or node == q: return node
      left = lca(node.left, p, q)
      right = lca(node.right, p, q)
      if left and right: return node   // split point
      return left or right

BST (use ordering):
  if p.val < node.val and q.val < node.val: go left
  elif p.val > node.val and q.val > node.val: go right
  else: return node                    // diverge point
```

### Pattern A8.5: Construct Tree from Traversals

```
PREORDER + INORDER:
  root = preorder[preIdx]
  Find root in inorder → splits into left/right subtrees
  root.left = build(inorder left portion)
  root.right = build(inorder right portion)
  
  Optimization: HashMap for O(1) inorder index lookup

PREORDER + POSTORDER (only works for full binary trees):
  More complex boundary tracking
```

### Pattern A8.6: Serialize / Deserialize

```
PREORDER WITH NULL MARKERS:
  serialize: val + "," for each node; "null," for null
  deserialize: queue of tokens
      val = queue.poll()
      if val == "null": return null
      node = new TreeNode(val)
      node.left = deserialize(queue)
      node.right = deserialize(queue)
      return node
```

### Pattern A8.7: BST Properties

```
VALIDATE BST:
  def isValid(node, lo=-∞, hi=+∞):
      if not node: return true
      if node.val <= lo or node.val >= hi: return false
      return isValid(node.left, lo, node.val) and
             isValid(node.right, node.val, hi)

KTH SMALLEST: inorder traversal, count to k (or use augmented BST with size)

BST ITERATOR: stack-based controlled inorder
  init: push all lefts
  next: pop, push all lefts of right child
  hasNext: stack not empty
```

### Pattern A8.8: Morris Traversal (O(1) Space Inorder)

```
curr = root
while curr:
    if not curr.left:
        visit(curr)
        curr = curr.right
    else:
        pred = inorder_predecessor(curr)   // rightmost in left subtree
        if pred.right == null:
            pred.right = curr              // create thread
            curr = curr.left
        else:
            pred.right = null              // remove thread
            visit(curr)
            curr = curr.right
```

---

## A9. TRIE

### Pattern A9.1: Basic Trie (Insert / Search / StartsWith)

```
class TrieNode:
    children = new TrieNode[26]  // or HashMap for Unicode
    isEnd = false

insert(word):
    node = root
    for c in word:
        idx = c - 'a'
        if not node.children[idx]: node.children[idx] = new TrieNode()
        node = node.children[idx]
    node.isEnd = true

search(word): traverse, check isEnd at last char
startsWith(prefix): traverse, return true if all chars exist (don't check isEnd)
```

```
Words: ["app", "apple", "api", "bat"]

        root
       /    \
      a      b
      |      |
      p      a
     / \     |
    p   i    t(end)
    |  (end)
    l
    |
    e(end)
   (end)
```

### Pattern A9.2: Wildcard Search with '.'

```
search(word, node, idx):
    if idx == len(word): return node.isEnd
    if word[idx] == '.':
        for each non-null child:
            if search(word, child, idx+1): return true
        return false
    else:
        child = node.children[word[idx]]
        return child and search(word, child, idx+1)
```

### Pattern A9.3: Word Search II (Trie + Grid Backtracking)

```
Build trie from word list
for each cell (i,j) in grid:
    dfs(i, j, trieNode):
        if trieNode.word exists: add to results, remove from trie (prune!)
        mark (i,j) visited
        for 4 directions:
            if valid and trieNode has child for grid[ni][nj]:
                dfs(ni, nj, child)
        unmark (i,j)
```

### Pattern A9.4: XOR Trie (Maximum XOR Pair)

```
Build binary trie from MSB to LSB (32 levels)
For max XOR with query x:
    for bit from 31 to 0:
        desired = 1 - bit_of_x   // want opposite to maximize XOR
        if child[desired] exists: go there
        else: go other way

Result: O(n * 32) = O(n) for finding max XOR pair
```

### Pattern A9.5: Autocomplete / Search Suggestions

```
Build trie with frequency/priority at each end-node
For each character typed:
    Navigate to prefix node
    DFS/BFS from node to collect top-k suggestions
    Sort by frequency/lexicographic order
```

---

## A10. MATRIX

### Pattern A10.1: Spiral Traversal

```
top, bottom, left, right = 0, m-1, 0, n-1
while top <= bottom and left <= right:
    for i in left..right:   result.add(matrix[top][i])     // →
    top++
    for i in top..bottom:   result.add(matrix[i][right])   // ↓
    right--
    if top <= bottom:
        for i in right..left: result.add(matrix[bottom][i]) // ←
        bottom--
    if left <= right:
        for i in bottom..top: result.add(matrix[i][left])   // ↑
        left++
```

### Pattern A10.2: Rotate Matrix 90° (Transpose + Reverse)

```
CLOCKWISE 90°:
  1. Transpose: swap matrix[i][j] with matrix[j][i]
  2. Reverse each row

COUNTER-CLOCKWISE 90°:
  1. Transpose
  2. Reverse each column (or: reverse rows then transpose)

180°: Reverse all rows, then reverse each row
```

```
[1,2,3]   transpose   [1,4,7]   reverse rows   [7,4,1]
[4,5,6]   -------->   [2,5,8]   ------------>   [8,5,2]
[7,8,9]               [3,6,9]                   [9,6,3]
```

### Pattern A10.3: Search in Sorted Matrix

```
ROW+COL SORTED (240 - Search a 2D Matrix II):
  Start from TOP-RIGHT (or bottom-left):
  row = 0, col = n-1
  while row < m and col >= 0:
      if matrix[row][col] == target: found!
      elif matrix[row][col] > target: col--   // too big, go left
      else: row++                              // too small, go down
  Complexity: O(m + n)

ROW-MAJOR SORTED (74 - Search a 2D Matrix):
  Treat as 1D array: idx → (idx/cols, idx%cols)
  Standard binary search: O(log(m*n))
```

### Pattern A10.4: Island Problems (DFS/BFS Flood Fill)

```
count = 0
for i in range(m):
    for j in range(n):
        if grid[i][j] == '1':
            count++
            flood_fill(i, j)       // mark entire island visited

flood_fill(i, j):
    if out_of_bounds or grid[i][j] != '1': return
    grid[i][j] = '0'              // mark visited (modify in-place)
    flood_fill(i±1, j)
    flood_fill(i, j±1)

VARIANTS:
  Max Area: return size from dfs
  Perimeter: count edges touching water/boundary
  Surrounded Regions: BFS from borders first, then flip interior
  Distinct Islands: normalize shape (canonical form via path string)
```

### Pattern A10.5: Grid DP (Paths, Cost, Square)

```
UNIQUE PATHS:     dp[i][j] = dp[i-1][j] + dp[i][j-1]
MIN PATH SUM:     dp[i][j] = grid[i][j] + min(dp[i-1][j], dp[i][j-1])
MAXIMAL SQUARE:   if matrix[i][j] == '1':
                      dp[i][j] = min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1]) + 1

MAXIMAL RECTANGLE: for each row, compute histogram heights → apply largest rectangle

Space optimization: use 1D dp array (previous row only)
```

### Pattern A10.6: Set Matrix Zeroes (In-Place Marking)

```
Use FIRST ROW and FIRST COLUMN as markers:
  1. Record if first row/col themselves have zeros (separate booleans)
  2. Scan rest: if matrix[i][j]==0 → set matrix[i][0]=0, matrix[0][j]=0
  3. Use markers to zero out cells (iterate inner matrix)
  4. Handle first row/col last using saved booleans

Complexity: O(mn) time, O(1) space
```

### Pattern A10.7: Diagonal Traversal

```
Key insight: elements on same diagonal share same (i + j) value
  Anti-diagonal: same (i - j) value

for d in range(m + n - 1):
    if d is even: traverse upward (row--, col++)
    if d is odd:  traverse downward (row++, col--)
    Calculate starting position based on boundary
```

### Pattern A10.8: Game of Life (In-Place State Encoding)

**Signal:** Update cells simultaneously based on neighbor state.

```
Encode transitions in unused bits:
  0 → 0: stays 0 (encode as 0)
  1 → 0: was 1, now 0 (encode as 1, since bit0 = old state)
  0 → 1: was 0, now 1 (encode as 2, bit1 = new state)
  1 → 1: stays 1 (encode as 3)

Count neighbors using (cell & 1) for old state
After all updates: cell >>= 1 to get new state
```

---

# PART B: ALGORITHMIC PATTERNS

---

## PATTERN SELECTION DECISION TREE

```
START: What does the problem ask?
│
├─ "Find pair/triplet with property" ──────────── TWO POINTERS (sorted) or HASH MAP
│
├─ "Contiguous subarray/substring with property"
│   ├─ Window size fixed? ─────────────────────── FIXED SLIDING WINDOW
│   ├─ Window size variable? ──────────────────── VARIABLE SLIDING WINDOW
│   └─ Exact sum / count? ────────────────────── PREFIX SUM + HASHMAP
│
├─ "Find position / boundary / minimum satisfying"
│   └─ Sorted or monotonic property? ─────────── BINARY SEARCH
│
├─ "Count ways / min cost / optimal value"
│   ├─ Optimal substructure + overlapping? ────── DYNAMIC PROGRAMMING
│   └─ Local optimal = global optimal? ───────── GREEDY
│
├─ "Generate all combinations / permutations"──── BACKTRACKING
│
├─ "Shortest path / connected / reachable"
│   ├─ Unweighted? ───────────────────────────── BFS
│   ├─ Weighted, no negative? ────────────────── DIJKSTRA
│   ├─ Negative weights? ─────────────────────── BELLMAN-FORD
│   └─ Dependencies / ordering? ──────────────── TOPOLOGICAL SORT
│
├─ "Next greater/smaller element" ────────────── MONOTONIC STACK
│
├─ "Top K / Kth largest / streaming" ─────────── HEAP / QUICKSELECT
│
├─ "Prefix-based lookup / autocomplete" ──────── TRIE
│
├─ "Range queries with updates" ──────────────── SEGMENT TREE / BIT
│
├─ "Group / connect / merge components" ──────── UNION-FIND
│
└─ "Design a data structure" ─────────────────── COMPOSITE DATA STRUCTURES
```

---

## 1. TWO POINTERS

### Mental Model
Two pointers exploit **sorted order** or **structural constraints** to reduce O(n²) to O(n).

```
Pattern Variants:
┌─────────────────────────────────────────────────────────┐
│  1. Opposite ends (converging)  ←─────────→             │
│  2. Same direction (fast/slow)  →─→                     │
│  3. Two arrays (merge-style)    arr1→  arr2→            │
└─────────────────────────────────────────────────────────┘
```

### Pattern 1.1: Opposite Ends (Converge)

**Signal:** Array is sorted (or can be sorted), find pair with sum/property.

```
left = 0, right = n - 1
while left < right:
    current = compute(left, right)
    if current == target: return result
    elif current < target: left++      // need more
    else: right--                       // need less
```

**Problems:** Two Sum II, 3Sum, Container With Most Water, Trapping Rain Water

### Pattern 1.2: Same Direction (Fast/Slow)

**Signal:** Remove duplicates, partition, detect cycle, find middle.

```
slow = 0
for fast in range(n):
    if condition(arr[fast]):
        arr[slow] = arr[fast]
        slow++
```

**Problems:** Remove Duplicates, Move Zeroes, Linked List Cycle

### Pattern 1.3: Three Pointers (3Sum Pattern)

**Signal:** Find triplets summing to target.

```
sort(nums)
for i in range(n-2):
    if i > 0 and nums[i] == nums[i-1]: continue  // skip duplicates
    left, right = i + 1, n - 1
    while left < right:
        total = nums[i] + nums[left] + nums[right]
        if total == 0: collect, skip dups, left++, right--
        elif total < 0: left++
        else: right--
```

**Complexity:** O(n²) time, O(1) space

### Pattern 1.4: Trapping Rain Water (Max from Both Sides)

**Signal:** Height-bounded capacity between elements.

```
left, right = 0, n-1
leftMax, rightMax = 0, 0
water = 0
while left < right:
    if height[left] < height[right]:
        leftMax = max(leftMax, height[left])
        water += leftMax - height[left]
        left++
    else:
        rightMax = max(rightMax, height[right])
        water += rightMax - height[right]
        right--
```

```
Visualization:
   |
   |  |      |
|  |  |  |   |  |
|__|__|__|_|__|__|   water fills between bars
```

---

## 2. SLIDING WINDOW

### Mental Model
Maintain a **window** [left, right] over a contiguous subarray/substring. Expand right to include, shrink left to maintain constraint.

```
┌─────────────────────────────────────────────────────┐
│           FIXED WINDOW        VARIABLE WINDOW       │
│         ├────k────┤          ├───?───┤              │
│    ───→ slide by 1     expand right, shrink left    │
└─────────────────────────────────────────────────────┘
```

### Pattern 2.1: Fixed-Size Window

**Signal:** "Subarray/substring of size k", "maximum sum of k elements".

```
// Build initial window
for i in range(k): windowSum += nums[i]

// Slide
for i in range(k, n):
    windowSum += nums[i] - nums[i - k]   // add new, remove old
    result = max(result, windowSum)
```

**Problems:** Max Sum Subarray of Size K, Max Vowels in Substring of Size K

### Pattern 2.2: Variable Window - Shrink When Invalid

**Signal:** "Longest substring/subarray with at most K distinct", "longest with constraint".

```
left = 0
for right in range(n):
    // expand: add nums[right] to window state
    while window is INVALID:
        // shrink: remove nums[left] from window state
        left++
    result = max(result, right - left + 1)
```

**Problems:** Longest Substring Without Repeating Characters, Longest Repeating Character Replacement, Fruits Into Baskets

### Pattern 2.3: Variable Window - Shrink to Minimize

**Signal:** "Smallest window containing X", "minimum length subarray with sum >= K".

```
left = 0, minLen = infinity
for right in range(n):
    // expand: add to window
    while window is VALID:
        minLen = min(minLen, right - left + 1)
        // shrink: remove from left
        left++
```

**Problems:** Minimum Window Substring, Minimum Size Subarray Sum

### Pattern 2.4: Window with Frequency Map

**Signal:** Anagram detection, permutation in string.

```
need = Counter(pattern)
have = 0, required = len(need)
left = 0
windowCounts = {}

for right in range(n):
    c = s[right]
    windowCounts[c] += 1
    if windowCounts[c] == need[c]: have++

    while have == required:
        // valid window found at [left, right]
        // shrink
        d = s[left]
        windowCounts[d] -= 1
        if windowCounts[d] < need[d]: have--
        left++
```

**Problems:** Find All Anagrams, Permutation in String, Minimum Window Substring

### Decision Matrix:

| Question | Pattern |
|----------|---------|
| Fixed size k? | Fixed window |
| Longest valid? | Expand + shrink when invalid |
| Shortest valid? | Expand + shrink while valid |
| Contains all chars? | Frequency map + have/need counters |

---

## 3. BINARY SEARCH

### Mental Model
Binary search is NOT just "find element in sorted array." It's **finding the boundary** where a predicate changes from false to true.

```
FALSE FALSE FALSE | TRUE TRUE TRUE TRUE
                  ^
        answer = first TRUE (or last FALSE)
```

### Pattern 3.1: Classic Search

```
left, right = 0, n - 1
while left <= right:
    mid = left + (right - left) / 2
    if nums[mid] == target: return mid
    elif nums[mid] < target: left = mid + 1
    else: right = mid - 1
return -1
```

### Pattern 3.2: First True (Lower Bound)

**Signal:** "First position where condition is true", "minimum value satisfying".

```
left, right = lo, hi
while left < right:
    mid = left + (right - left) / 2
    if condition(mid):
        right = mid        // mid might be answer, search left
    else:
        left = mid + 1     // mid is not answer
return left                // first position where condition is true
```

### Pattern 3.3: Last True (Upper Bound)

```
left, right = lo, hi
while left < right:
    mid = left + (right - left + 1) / 2   // ceil to avoid infinite loop
    if condition(mid):
        left = mid         // mid might be answer, search right
    else:
        right = mid - 1
return left
```

### Pattern 3.4: Search on Answer (Binary Search on Result)

**Signal:** "Minimize the maximum", "find minimum capacity such that...", "can we achieve X?"

```
left, right = min_possible, max_possible
while left < right:
    mid = left + (right - left) / 2
    if canAchieve(mid):        // feasibility check
        right = mid            // try smaller
    else:
        left = mid + 1         // need larger
return left

// canAchieve is problem-specific: simulate with capacity=mid, check if valid
```

**Problems:** Koko Eating Bananas, Split Array Largest Sum, Ship Packages in D Days, Magnetic Force Between Balls

```
Example: Koko Eating Bananas
  piles = [3, 6, 7, 11], hours = 8
  
  Binary search on speed k: [1, 11]
  canFinish(k): sum(ceil(pile/k)) <= hours
  
  k=6: ceil(3/6)+ceil(6/6)+ceil(7/6)+ceil(11/6) = 1+1+2+2 = 6 <= 8 ✓
  k=3: 1+2+3+4 = 10 > 8 ✗
  k=4: 1+2+2+3 = 8 <= 8 ✓ → answer = 4
```

### Pattern 3.5: Rotated Sorted Array

**Signal:** Array was sorted then rotated, find element or minimum.

```
Key insight: one half is always sorted.

left, right = 0, n - 1
while left <= right:
    mid = (left + right) / 2
    if nums[mid] == target: return mid

    if nums[left] <= nums[mid]:        // left half sorted
        if nums[left] <= target < nums[mid]:
            right = mid - 1            // target in left half
        else:
            left = mid + 1             // target in right half
    else:                              // right half sorted
        if nums[mid] < target <= nums[right]:
            left = mid + 1
        else:
            right = mid - 1
```

### Pattern 3.6: Peak Finding

```
left, right = 0, n - 1
while left < right:
    mid = (left + right) / 2
    if nums[mid] < nums[mid + 1]:
        left = mid + 1        // peak is to the right
    else:
        right = mid           // peak is here or to the left
return left
```

---

## 4. DYNAMIC PROGRAMMING

### Mental Model
DP = **Recursion + Memoization** = **Fill a table based on subproblem dependencies**.

```
┌──────────────────────────────────────────────────────────────┐
│  DP Pattern Taxonomy:                                         │
│                                                               │
│  ├── Linear DP (1D)                                          │
│  │   ├── Fibonacci / Climbing Stairs                         │
│  │   ├── House Robber (skip/take)                            │
│  │   └── LIS (Longest Increasing Subsequence)                │
│  │                                                           │
│  ├── Knapsack (subset selection with capacity)               │
│  │   ├── 0/1 Knapsack                                       │
│  │   ├── Unbounded Knapsack                                  │
│  │   ├── Subset Sum / Partition                              │
│  │   └── Coin Change                                         │
│  │                                                           │
│  ├── Two-String DP (2D)                                      │
│  │   ├── LCS (Longest Common Subsequence)                    │
│  │   ├── Edit Distance                                       │
│  │   ├── Regex / Wildcard Matching                           │
│  │   └── Interleaving String                                 │
│  │                                                           │
│  ├── Grid DP                                                 │
│  │   ├── Unique Paths                                        │
│  │   ├── Min Path Sum                                        │
│  │   └── Maximal Square / Rectangle                          │
│  │                                                           │
│  ├── Interval DP                                             │
│  │   ├── Burst Balloons                                      │
│  │   ├── Matrix Chain Multiplication                         │
│  │   └── Stone Game / Palindrome Partitioning                │
│  │                                                           │
│  ├── State Machine DP                                        │
│  │   ├── Stock Buy/Sell (with cooldown, fees, k transactions)│
│  │   └── Paint House / Robot paths with states               │
│  │                                                           │
│  ├── Tree DP                                                 │
│  │   ├── House Robber III                                    │
│  │   ├── Diameter / Max Path Sum                             │
│  │   └── Count nodes satisfying property                     │
│  │                                                           │
│  └── Bitmask DP (state compression)                          │
│      ├── TSP                                                 │
│      ├── Assign tasks to workers                             │
│      └── Shortest superstring                                │
└──────────────────────────────────────────────────────────────┘
```

### Pattern 4.1: Linear DP - Fibonacci Style

**Signal:** Answer at step n depends on previous 1-2 steps.

```
dp[0] = base, dp[1] = base
for i = 2 to n:
    dp[i] = dp[i-1] + dp[i-2]

Space optimization: keep only prev1, prev2
```

**Problems:** Climbing Stairs, Decode Ways, Tribonacci

### Pattern 4.2: Linear DP - Skip/Take (House Robber)

**Signal:** Choose elements with constraints (can't take adjacent).

```
dp[i] = max(
    dp[i-1],              // skip current
    dp[i-2] + nums[i]    // take current
)

Generalization: dp[i] = max(skip, take) where take = dp[valid_prev] + value[i]
```

**Problems:** House Robber I/II/III, Delete and Earn

### Pattern 4.3: Longest Increasing Subsequence (LIS)

**Signal:** Longest subsequence with ordering constraint.

```
O(n²) DP:
  dp[i] = length of LIS ending at i
  dp[i] = max(dp[j] + 1) for all j < i where nums[j] < nums[i]

O(n log n) with patience sorting:
  tails = []   // tails[i] = smallest tail of LIS of length i+1
  for num in nums:
      pos = bisect_left(tails, num)
      if pos == len(tails): tails.append(num)
      else: tails[pos] = num
  return len(tails)
```

```
nums: [10, 9, 2, 5, 3, 7, 101, 18]
tails evolution:
  [10]
  [9]
  [2]
  [2, 5]
  [2, 3]
  [2, 3, 7]
  [2, 3, 7, 101]
  [2, 3, 7, 18]     → LIS length = 4
```

### Pattern 4.4: 0/1 Knapsack

**Signal:** Select items with weight/cost constraint, maximize value. Each item used once.

```
dp[i][w] = max value using items 0..i with capacity w

dp[i][w] = max(
    dp[i-1][w],                    // skip item i
    dp[i-1][w - weight[i]] + val[i]  // take item i
)

1D optimization (iterate capacity backwards):
  for i in range(n):
      for w in range(W, weight[i]-1, -1):   // RIGHT TO LEFT
          dp[w] = max(dp[w], dp[w - weight[i]] + val[i])
```

**Problems:** Partition Equal Subset Sum, Target Sum, Last Stone Weight II

### Pattern 4.5: Unbounded Knapsack

**Signal:** Items can be used unlimited times.

```
for i in range(n):
    for w in range(weight[i], W+1):    // LEFT TO RIGHT (reuse allowed)
        dp[w] = max(dp[w], dp[w - weight[i]] + val[i])

Coin Change (minimize):
  dp[0] = 0
  for amount in range(1, target+1):
      for coin in coins:
          if coin <= amount:
              dp[amount] = min(dp[amount], dp[amount - coin] + 1)
```

**Problems:** Coin Change, Coin Change II (counting), Rod Cutting, Combination Sum IV

### Pattern 4.6: Two-String DP (LCS / Edit Distance)

**Signal:** Compare two sequences, find common/transform.

```
LCS:
  dp[i][j] = LCS of s1[0..i-1] and s2[0..j-1]
  if s1[i-1] == s2[j-1]: dp[i][j] = dp[i-1][j-1] + 1
  else: dp[i][j] = max(dp[i-1][j], dp[i][j-1])

Edit Distance:
  if s1[i-1] == s2[j-1]: dp[i][j] = dp[i-1][j-1]
  else: dp[i][j] = 1 + min(
      dp[i-1][j-1],    // replace
      dp[i-1][j],      // delete from s1
      dp[i][j-1]       // insert into s1
  )
```

```
    ""  h  o  r  s  e
""   0  1  2  3  4  5
r    1  1  2  2  3  4
o    2  2  1  2  3  4
s    3  3  2  2  2  3

Edit Distance("horse", "ros") = 3
```

**Problems:** LCS, Edit Distance, Distinct Subsequences, Interleaving String

### Pattern 4.7: Interval DP

**Signal:** Optimal way to split/merge a range [i..j], consider all split points.

```
// Fill diagonally: length 1, 2, 3, ...
for len = 2 to n:
    for i = 0 to n - len:
        j = i + len - 1
        for k = i to j - 1:             // all split points
            dp[i][j] = min/max(dp[i][k] + dp[k+1][j] + cost(i,j,k))
```

```
Burst Balloons:
  dp[i][j] = max coins from bursting all balloons in (i,j) exclusive
  dp[i][j] = max(dp[i][k] + dp[k][j] + nums[i]*nums[k]*nums[j])
             for k in (i+1, j-1)

  Think: "which balloon do I burst LAST in this range?"
```

**Problems:** Burst Balloons, Matrix Chain Multiplication, Palindrome Partitioning II, Strange Printer

### Pattern 4.8: State Machine DP (Stock Problems)

**Signal:** Multiple states/phases, transitions between states.

```
Stock Buy and Sell with K Transactions:

States: buy[k], sell[k] for transaction k
  buy[k]  = max(buy[k], sell[k-1] - price)   // buy on day (use prev sell)
  sell[k] = max(sell[k], buy[k] + price)      // sell on day

With Cooldown:
  buy  = max(buy, cooldown - price)
  sell = max(sell, buy + price)
  cooldown = max(cooldown, sell)              // must wait one day

Diagram:
  ┌──hold──┐     sell      ┌──rest──┐
  │  BUY   │───────────→   │  SOLD  │
  └────────┘                └────────┘
       ↑                         │
       │         cooldown        │
       └─────────────────────────┘
```

**Problems:** Best Time to Buy/Sell Stock I/II/III/IV, with Cooldown, with Fee

### Pattern 4.9: Grid DP

**Signal:** Count paths, min cost path in 2D grid.

```
Unique Paths:     dp[i][j] = dp[i-1][j] + dp[i][j-1]
Min Path Sum:     dp[i][j] = grid[i][j] + min(dp[i-1][j], dp[i][j-1])
Maximal Square:   dp[i][j] = min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1]) + 1

Space: O(n) using rolling array
```

### Pattern 4.10: Bitmask DP

**Signal:** Small set (n ≤ 20), track which elements are used.

```
dp[mask] = optimal value when elements in `mask` are used
mask is a binary number: bit i = 1 means element i is used

dp[mask | (1 << j)] = optimize(dp[mask], cost of adding j)

Example: Assign n tasks to n workers
  dp[mask] = min cost to assign first popcount(mask) tasks
              using workers indicated by mask
```

**Problems:** TSP, Shortest Superstring, Can I Win, Parallel Courses II

### DP Framework (How to Solve ANY DP Problem):

```
1. DEFINE STATE: What information do I need? → dp[?][?]
2. DEFINE TRANSITION: How do I compute dp[i] from smaller subproblems?
3. BASE CASE: What's the smallest subproblem answer?
4. ORDER: Fill table so dependencies are ready (bottom-up)
5. ANSWER: Where in the table is my final answer?
6. OPTIMIZE SPACE: Can I reduce dimensions? (rolling array)
```

---

## 5. GREEDY

### Mental Model
Greedy works when **local optimal choice leads to global optimal**. Prove by exchange argument or greedy stays ahead.

```
┌──────────────────────────────────────────────────────┐
│  Greedy Pattern Taxonomy:                             │
│                                                       │
│  ├── Interval Scheduling (sort by end/start)         │
│  ├── Huffman / Priority Selection (always pick best) │
│  ├── Exchange Argument (swap improves nothing)       │
│  ├── Fractional Knapsack (sort by ratio)             │
│  ├── Greedy + Max/Min Tracking (single pass)         │
│  └── Task Scheduling (heap + cooldown)               │
└──────────────────────────────────────────────────────┘
```

### Pattern 5.1: Interval Scheduling

**Signal:** Maximum non-overlapping intervals, minimum rooms/resources.

```
Maximum non-overlapping: sort by END time, greedily pick earliest ending
  sort intervals by end
  count = 0, lastEnd = -∞
  for [start, end] in intervals:
      if start >= lastEnd:
          count++
          lastEnd = end

Minimum meeting rooms: sort by START, use min-heap of end times
  sort by start
  heap = []
  for [start, end]:
      if heap and heap[0] <= start: heappop(heap)
      heappush(heap, end)
  return len(heap)
```

**Problems:** Non-Overlapping Intervals, Meeting Rooms II, Merge Intervals, Minimum Arrows to Burst Balloons

### Pattern 5.2: Jump Game / Reachability

**Signal:** Can you reach the end? Minimum jumps to reach end?

```
Jump Game I (can reach?):
  farthest = 0
  for i in range(n):
      if i > farthest: return false
      farthest = max(farthest, i + nums[i])
  return true

Jump Game II (min jumps):
  jumps = 0, curEnd = 0, farthest = 0
  for i in range(n - 1):
      farthest = max(farthest, i + nums[i])
      if i == curEnd:
          jumps++
          curEnd = farthest
  return jumps
```

### Pattern 5.3: Task Scheduler / Reorganize

**Signal:** Schedule with cooldown, rearrange with no adjacent same.

```
Task Scheduler:
  maxFreq = max frequency
  maxCount = number of elements with maxFreq
  result = max(n, (maxFreq - 1) * (interval + 1) + maxCount)

  Visualization (A=3, B=3, interval=2):
  A _ _ A _ _ A
  A B _ A B _ A B     ← fill gaps with next frequent

Reorganize String:
  Use max-heap, always place most frequent that isn't last placed
```

**Problems:** Task Scheduler, Reorganize String, Distant Barcodes

### Pattern 5.4: Partition Labels / Greedy Expand

**Signal:** Partition sequence into minimum parts where each element appears in only one part.

```
last = {c: i for i, c in enumerate(s)}   // last occurrence of each char
start = end = 0
result = []
for i, c in enumerate(s):
    end = max(end, last[c])
    if i == end:
        result.append(end - start + 1)
        start = i + 1
```

### Pattern 5.5: Gas Station (Circular Greedy)

**Signal:** Circular route, can we complete a full loop?

```
If total gas >= total cost, a solution exists.
Find starting point: reset whenever tank goes negative.

tank = 0, total = 0, start = 0
for i in range(n):
    diff = gas[i] - cost[i]
    tank += diff
    total += diff
    if tank < 0:
        start = i + 1
        tank = 0
return start if total >= 0 else -1
```

### Pattern 5.6: Candy / Two-Pass Assignment

**Signal:** Assign values with neighbor constraints.

```
Pass 1 (left to right): if rating[i] > rating[i-1], candy[i] = candy[i-1] + 1
Pass 2 (right to left): if rating[i] > rating[i+1], candy[i] = max(candy[i], candy[i+1] + 1)
```

---

## 6. BACKTRACKING

### Mental Model
Backtracking = DFS on a **decision tree**. At each node, make a choice, recurse, then **undo** the choice.

```
                    []
              /     |      \
           [1]     [2]     [3]
          / \       |
       [1,2] [1,3] [2,3]
        |
     [1,2,3]

Choose → Explore → Unchoose
```

### Pattern 6.1: Subsets (Power Set)

**Signal:** Generate all subsets.

```
def backtrack(start, current):
    result.add(copy(current))          // every node is valid
    for i in range(start, n):
        current.add(nums[i])           // choose
        backtrack(i + 1, current)      // explore
        current.remove(last)           // unchoose

// With duplicates: sort first, skip nums[i] == nums[i-1] when i > start
```

### Pattern 6.2: Permutations

**Signal:** Generate all orderings.

```
def backtrack(current):
    if len(current) == n: result.add(copy(current))
    for i in range(n):
        if used[i]: continue
        used[i] = true
        current.add(nums[i])
        backtrack(current)
        current.remove(last)
        used[i] = false

// With duplicates: sort, skip if nums[i]==nums[i-1] and !used[i-1]
```

### Pattern 6.3: Combination Sum

**Signal:** Find combinations summing to target.

```
def backtrack(start, remaining, current):
    if remaining == 0: result.add(copy(current))
    if remaining < 0: return
    for i in range(start, n):
        current.add(nums[i])
        backtrack(i, remaining - nums[i], current)     // i for reuse, i+1 for no reuse
        current.remove(last)
```

### Pattern 6.4: Board/Grid Search (N-Queens, Sudoku, Word Search)

**Signal:** Place items on board with constraints, or find path in grid.

```
N-Queens:
  def backtrack(row):
      if row == n: result.add(board)
      for col in range(n):
          if isValid(row, col):          // check col, diag, anti-diag
              placeQueen(row, col)
              backtrack(row + 1)
              removeQueen(row, col)

  Validity: use sets for columns, diagonals (row-col), anti-diagonals (row+col)

Sudoku Solver:
  Find empty cell → try 1-9 → check row/col/box → recurse → backtrack
```

### Pattern 6.5: Palindrome Partitioning

**Signal:** Partition string into valid segments.

```
def backtrack(start, current):
    if start == n: result.add(copy(current))
    for end in range(start + 1, n + 1):
        if isPalindrome(s[start:end]):
            current.add(s[start:end])
            backtrack(end, current)
            current.remove(last)
```

### Backtracking Optimization Techniques:

| Technique | When | How |
|-----------|------|-----|
| Sort + Skip duplicates | Input has duplicates | `if i > start and nums[i] == nums[i-1]: continue` |
| Pruning | Can detect dead ends early | `if remaining < 0: return` |
| Constraint propagation | Sudoku/N-Queens | Maintain valid options per cell |
| Trie-guided search | Word Search II | Only explore paths matching trie prefix |

---

## 7. GRAPHS

### Mental Model

```
┌──────────────────────────────────────────────────────────────────┐
│  Graph Algorithm Selection:                                       │
│                                                                   │
│  Traversal:        BFS (shortest in unweighted), DFS (explore all)│
│  Connectivity:     Union-Find, DFS/BFS connected components       │
│  Shortest Path:    Dijkstra, Bellman-Ford, Floyd-Warshall, BFS    │
│  Ordering:         Topological Sort (DAG)                         │
│  MST:              Kruskal's (sort edges), Prim's (grow tree)     │
│  Cycle Detection:  DFS coloring (directed), Union-Find (undirected)│
│  Strong Components: Tarjan's, Kosaraju's                          │
└──────────────────────────────────────────────────────────────────┘
```

### Pattern 7.1: BFS - Shortest Path in Unweighted Graph

```
def bfs(start, target):
    queue = deque([(start, 0)])
    visited = {start}
    while queue:
        node, dist = queue.popleft()
        if node == target: return dist
        for neighbor in graph[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, dist + 1))
    return -1
```

**Problems:** Word Ladder, Shortest Path in Binary Matrix, Open the Lock

### Pattern 7.2: BFS - Multi-Source

**Signal:** Propagation from multiple starting points simultaneously.

```
queue = deque()
for all sources:
    queue.append((source, 0))
    visited.add(source)
// Standard BFS from here - all sources expand simultaneously
```

**Problems:** Rotting Oranges, Walls and Gates, 01 Matrix

### Pattern 7.3: DFS - Connected Components / Flood Fill

```
def dfs(node):
    visited.add(node)
    for neighbor in graph[node]:
        if neighbor not in visited:
            dfs(neighbor)

// Count components:
count = 0
for node in all_nodes:
    if node not in visited:
        count++
        dfs(node)
```

**Problems:** Number of Islands, Number of Provinces, Max Area of Island

### Pattern 7.4: DFS - Cycle Detection

```
Directed Graph (3-color):
  WHITE = unvisited, GRAY = in current path, BLACK = fully processed

  def hasCycle(node):
      color[node] = GRAY
      for neighbor in graph[node]:
          if color[neighbor] == GRAY: return true    // back edge!
          if color[neighbor] == WHITE:
              if hasCycle(neighbor): return true
      color[node] = BLACK
      return false

Undirected Graph:
  def dfs(node, parent):
      visited.add(node)
      for neighbor in graph[node]:
          if neighbor == parent: continue
          if neighbor in visited: return true        // cycle!
          if dfs(neighbor, node): return true
      return false
```

**Problems:** Course Schedule, Detect Cycle in Graph, Redundant Connection

### Pattern 7.5: DFS - Backtracking on Graph (All Paths)

```
def allPaths(node, target, path):
    if node == target:
        result.add(copy(path))
        return
    for neighbor in graph[node]:
        path.add(neighbor)
        allPaths(neighbor, target, path)
        path.remove(last)
```

**Problems:** All Paths from Source to Target

### Pattern 7.6: Bipartite Check (2-Coloring)

```
def isBipartite(graph):
    color = {}
    for node in range(n):
        if node in color: continue
        queue = deque([node])
        color[node] = 0
        while queue:
            curr = queue.popleft()
            for neighbor in graph[curr]:
                if neighbor not in color:
                    color[neighbor] = 1 - color[curr]
                    queue.append(neighbor)
                elif color[neighbor] == color[curr]:
                    return false
    return true
```

### Pattern 7.7: Clone Graph

```
visited = {}  // original -> clone mapping

def clone(node):
    if node in visited: return visited[node]
    copy = Node(node.val)
    visited[node] = copy
    for neighbor in node.neighbors:
        copy.neighbors.add(clone(neighbor))
    return copy
```

---

## 8. TREES (Advanced)

### Pattern 8.1: Tree DP (Combine Children Results)

**Signal:** Optimization on tree where answer at node depends on subtree answers.

```
General Template:
  def dfs(node):
      if not node: return base_value
      left = dfs(node.left)
      right = dfs(node.right)

      // Update global answer using both branches
      globalAns = optimize(globalAns, combine(left, right, node))

      // Return single-branch value to parent
      return singleBranch(left, right, node)
```

```
Max Path Sum:
  left = max(0, dfs(left))     // ignore negative branches
  right = max(0, dfs(right))
  globalMax = max(globalMax, left + right + node.val)   // through node
  return max(left, right) + node.val                     // up to parent

Diameter:
  globalMax = max(globalMax, left + right)               // edges through node
  return max(left, right) + 1                            // height
```

### Pattern 8.2: BST Properties

```
Key Property: inorder traversal of BST = sorted array

Validate BST:
  def isValid(node, lo, hi):
      if not node: return true
      if node.val <= lo or node.val >= hi: return false
      return isValid(node.left, lo, node.val) and
             isValid(node.right, node.val, hi)

Kth Smallest: inorder traversal, count to k
BST Iterator: controlled inorder using stack (push all lefts)
```

### Pattern 8.3: Serialize / Deserialize

```
Preorder with null markers:
  serialize: node.val + "," + ser(left) + "," + ser(right), use "null" for null

  deserialize: consume values from queue
      val = queue.poll()
      if val == "null": return null
      node = new TreeNode(val)
      node.left = deserialize(queue)
      node.right = deserialize(queue)
      return node
```

---

## 9. UNION-FIND (Disjoint Set Union)

### Mental Model
Union-Find tracks **connected components** with near O(1) union and find operations.

```
┌───┐  ┌───┐  ┌───┐        union(1,2)      ┌───┐  ┌───┐
│ 1 │  │ 2 │  │ 3 │   ──────────────→       │1,2│  │ 3 │
└───┘  └───┘  └───┘                          └───┘  └───┘
```

### Template:

```java
class UnionFind {
    int[] parent, rank;
    int components;

    UnionFind(int n) {
        parent = new int[n];
        rank = new int[n];
        components = n;
        for (int i = 0; i < n; i++) parent[i] = i;
    }

    int find(int x) {
        if (parent[x] != x)
            parent[x] = find(parent[x]);  // path compression
        return parent[x];
    }

    boolean union(int x, int y) {
        int px = find(x), py = find(y);
        if (px == py) return false;       // already connected
        if (rank[px] < rank[py]) { parent[px] = py; }
        else if (rank[px] > rank[py]) { parent[py] = px; }
        else { parent[py] = px; rank[px]++; }
        components--;
        return true;
    }
}
```

### When to Use Union-Find:

| Signal | Example |
|--------|---------|
| "Are X and Y connected?" | Graph Valid Tree |
| "How many connected components?" | Number of Connected Components |
| "Union operations dynamically" | Accounts Merge |
| "Detect cycle in undirected graph" | Redundant Connection |
| "Kruskal's MST" | Min Cost to Connect All Points |
| "Dynamic connectivity" | Number of Islands II (online) |

**Problems:** Accounts Merge, Redundant Connection, Graph Valid Tree, Longest Consecutive Sequence, Number of Islands II, Swim in Rising Water

---

## 10. DIVIDE AND CONQUER

### Mental Model
Split problem into subproblems, solve independently, merge results.

```
solve(problem):
    if base_case: return trivial_answer
    left = solve(left_half)
    right = solve(right_half)
    return merge(left, right)
```

### Pattern 10.1: Merge Sort Based

**Signal:** Count inversions, count smaller numbers after self.

```
Count Inversions (during merge sort):
  merge(left, right):
      i = j = 0, inversions = 0
      while i < len(left) and j < len(right):
          if left[i] <= right[j]: result.add(left[i]); i++
          else:
              result.add(right[j]); j++
              inversions += len(left) - i   // all remaining left > right[j]
```

### Pattern 10.2: Quick Select (Kth Element)

```
def quickselect(nums, k):
    pivot = random choice
    less, equal, greater = partition around pivot
    if k <= len(less): return quickselect(less, k)
    elif k <= len(less) + len(equal): return pivot
    else: return quickselect(greater, k - len(less) - len(equal))

Average O(n), Worst O(n²) — randomization makes worst case unlikely
```

### Pattern 10.3: Closest Pair of Points

```
Sort by x-coordinate
Divide into left and right halves
Recursively find closest pair in each half
Check strip around dividing line for cross-pairs
Combine: min of left, right, and strip
O(n log n) time
```

---

## 11. BIT MANIPULATION

### Mental Model

```
Key Operations:
  x & (x-1)     → clear lowest set bit     (count bits, power of 2)
  x & (-x)      → isolate lowest set bit   (BIT/Fenwick)
  x ^ x = 0     → self-cancellation        (find unique)
  x | (1 << i)  → set bit i
  x & (1 << i)  → check bit i
  x ^ (1 << i)  → toggle bit i
```

### Pattern 11.1: Single Number (XOR Cancellation)

**Signal:** All elements appear twice except one.

```
result = 0
for num in nums:
    result ^= num
return result    // pairs cancel, unique remains

Two unique numbers:
  xor = a ^ b  (the two unique numbers XORed)
  diff = xor & (-xor)   // rightmost different bit
  Split nums into two groups by this bit → XOR each group
```

**Problems:** Single Number I/II/III

### Pattern 11.2: Counting Bits

```
Kernighan's (count set bits):
  count = 0
  while n:
      n &= (n - 1)     // clear lowest set bit
      count++

DP approach (count bits 0..n):
  dp[i] = dp[i >> 1] + (i & 1)
  // or dp[i] = dp[i & (i-1)] + 1
```

### Pattern 11.3: Subsets via Bitmask

```
for mask in range(1 << n):     // 2^n subsets
    subset = []
    for i in range(n):
        if mask & (1 << i):
            subset.add(nums[i])
```

### Pattern 11.4: Bitwise AND of Range

```
// Find common prefix of left and right
while left != right:
    left >>= 1
    right >>= 1
    shift++
return left << shift
```

---

## 12. MONOTONIC STACK / QUEUE

### Mental Model
Maintain a stack/queue where elements are always in sorted order (increasing or decreasing). Used to efficiently find **next greater/smaller** or **sliding window extremes**.

```
Monotonic Decreasing Stack:
  Elements: [8, 5, 3, ...]  (top is smallest)
  When new element > top: pop until stack is valid
  Popped elements found their "next greater" = new element

  ┌───┐
  │ 3 │ ← top (smallest)
  │ 5 │
  │ 8 │
  └───┘
  New: 6 → pop 3 (next greater = 6), pop 5 (next greater = 6), push 6
```

### Pattern 12.1: Next Greater Element

```
stack = []   // indices, maintaining decreasing values
result = [-1] * n
for i in range(n):
    while stack and nums[i] > nums[stack[-1]]:
        result[stack.pop()] = nums[i]
    stack.append(i)
```

### Pattern 12.2: Largest Rectangle in Histogram

```
stack = [-1]   // sentinel
maxArea = 0
for i in range(n + 1):
    h = heights[i] if i < n else 0
    while stack[-1] != -1 and h <= heights[stack[-1]]:
        height = heights[stack.pop()]
        width = i - stack[-1] - 1
        maxArea = max(maxArea, height * width)
    stack.append(i)
```

### Pattern 12.3: Monotonic Queue (Sliding Window Maximum)

```
deque = []  // front = maximum, stores indices
for i in range(n):
    // remove out-of-window from front
    while deque and deque[0] <= i - k: deque.popleft()
    // maintain decreasing order from back
    while deque and nums[deque[-1]] <= nums[i]: deque.pop()
    deque.append(i)
    if i >= k - 1: result.append(nums[deque[0]])
```

### Pattern 12.4: Sum of Subarray Minimums

```
// For each element, find how many subarrays it's the minimum of
// Use monotonic stack to find previous less element (PLE) and next less element (NLE)
// Contribution of nums[i] = nums[i] * (i - PLE[i]) * (NLE[i] - i)
```

---

## 13. HEAP (Advanced Patterns)

### Pattern 13.1: Two Heaps (Median)

```
MaxHeap (left half) | MinHeap (right half)
    [smaller half]  |  [larger half]

Invariant: maxHeap.size >= minHeap.size >= maxHeap.size - 1
Median = maxHeap.peek() or avg(both peeks)
```

### Pattern 13.2: K-Way Merge

```
Initialize heap with first element from each of K sorted sources
Repeat:
    pop minimum from heap → add to result
    push next element from same source
```

### Pattern 13.3: Lazy Deletion

```
When you need to "remove" specific elements from heap:
  deleted = set/map
  On pop: while top is in deleted, pop and discard
  On "remove": just add to deleted set
```

### Pattern 13.4: Top-K with Min-Heap of Size K

```
Maintain min-heap of size K
For each element:
    if heap.size < K: push
    elif element > heap.peek(): pop, push
Final heap contains K largest (peek = Kth largest)
```

---

## 14. TRIE (Advanced Patterns)

### Pattern 14.1: Autocomplete / Search Suggestions

```
Build trie from dictionary
For each prefix character typed:
    Navigate to prefix node
    DFS/BFS from that node to collect top suggestions
    (Store frequency/priority at nodes for ranking)
```

### Pattern 14.2: XOR Maximum (Binary Trie)

```
Insert numbers bit by bit (MSB to LSB, 32 levels)
To find max XOR with query:
    At each level, try to go opposite direction (maximize XOR bit)
    If can't, go same direction
```

### Pattern 14.3: Word Search II (Trie + Backtracking)

```
Build trie from word list
DFS from each grid cell, following trie edges
Prune: if no trie child for current char, skip
Optimization: remove found words from trie to avoid re-finding
```

---

## 15. SEGMENT TREE / BIT (Binary Indexed Tree)

### Mental Model

```
Segment Tree: each node stores aggregate for a range
              used for range queries + point/range updates

                    [0-7] sum=36
                  /            \
           [0-3] sum=10      [4-7] sum=26
           /      \           /      \
      [0-1]=3  [2-3]=7  [4-5]=11  [6-7]=15
      /   \    /   \     /   \     /   \
    [0]  [1] [2] [3]  [4] [5]  [6] [7]
     1    2   3   4    5   6    7   8

BIT/Fenwick Tree: uses bit manipulation for prefix sums
  More compact, but only supports prefix operations
```

### Segment Tree Template:

```
build(node, start, end):
    if start == end: tree[node] = arr[start]; return
    mid = (start + end) / 2
    build(2*node, start, mid)
    build(2*node+1, mid+1, end)
    tree[node] = tree[2*node] + tree[2*node+1]

query(node, start, end, l, r):
    if r < start or end < l: return 0           // out of range
    if l <= start and end <= r: return tree[node] // fully in range
    mid = (start + end) / 2
    return query(left, start, mid, l, r) + query(right, mid+1, end, l, r)

update(node, start, end, idx, val):
    if start == end: tree[node] = val; return
    mid = (start + end) / 2
    if idx <= mid: update(left, start, mid, idx, val)
    else: update(right, mid+1, end, idx, val)
    tree[node] = tree[2*node] + tree[2*node+1]
```

### BIT (Fenwick Tree) Template:

```
// Prefix sum queries + point updates in O(log n)
update(i, delta):
    while i <= n:
        bit[i] += delta
        i += i & (-i)       // add lowest set bit

query(i):                    // prefix sum [1..i]
    sum = 0
    while i > 0:
        sum += bit[i]
        i -= i & (-i)       // remove lowest set bit
    return sum

rangeQuery(l, r) = query(r) - query(l - 1)
```

### When to Use:

| Need | Structure |
|------|-----------|
| Range sum + point update | BIT (simpler) |
| Range min/max + point update | Segment Tree |
| Range update + range query | Segment Tree with Lazy Propagation |
| Count inversions | BIT |
| Count smaller numbers after self | BIT / Segment Tree |

---

## 16. TOPOLOGICAL SORT

### Mental Model
Linear ordering of vertices in a DAG such that for every edge u→v, u comes before v.

```
    A → B → D
    ↓       ↑
    C ──────┘

Topological orders: [A, C, B, D] or [A, B, C, D]
```

### Pattern 16.1: Kahn's Algorithm (BFS-based)

```
// Compute in-degrees
inDegree = [0] * n
for each edge (u, v): inDegree[v]++

// Start with all zero in-degree nodes
queue = [node for node if inDegree[node] == 0]
order = []

while queue:
    node = queue.popleft()
    order.append(node)
    for neighbor in graph[node]:
        inDegree[neighbor]--
        if inDegree[neighbor] == 0:
            queue.append(neighbor)

if len(order) != n: CYCLE EXISTS (not a DAG)
```

### Pattern 16.2: DFS-based Topological Sort

```
visited = set()
stack = []  // result in reverse

def dfs(node):
    visited.add(node)
    for neighbor in graph[node]:
        if neighbor not in visited:
            dfs(neighbor)
    stack.append(node)   // add AFTER all descendants

for node in all_nodes:
    if node not in visited: dfs(node)
return stack.reversed()
```

### When to Use:

| Signal | Example |
|--------|---------|
| Course prerequisites | Course Schedule I/II |
| Build order / compilation | Task dependencies |
| Alien dictionary | Derive order from sorted words |
| Parallel courses | Minimum semesters |
| Can tasks form valid order? | Check if DAG |

**Problems:** Course Schedule I/II, Alien Dictionary, Parallel Courses, Build Matrix with Conditions

---

## 17. SHORTEST PATH ALGORITHMS

### Decision Matrix:

| Scenario | Algorithm | Complexity |
|----------|-----------|------------|
| Unweighted graph | BFS | O(V + E) |
| Non-negative weights | Dijkstra | O((V+E) log V) |
| Negative weights, no neg cycle | Bellman-Ford | O(V * E) |
| All-pairs shortest path | Floyd-Warshall | O(V³) |
| DAG | Topological sort + relax | O(V + E) |

### Pattern 17.1: Dijkstra's Algorithm

```
def dijkstra(graph, source):
    dist = {node: infinity for node in graph}
    dist[source] = 0
    pq = [(0, source)]   // (distance, node)

    while pq:
        d, u = heappop(pq)
        if d > dist[u]: continue    // stale entry
        for v, weight in graph[u]:
            if dist[u] + weight < dist[v]:
                dist[v] = dist[u] + weight
                heappush(pq, (dist[v], v))
    return dist
```

```
Visualization:
    A ──2──→ B ──1──→ D
    |        ↑        ↑
    4        3        2
    ↓        |        |
    C ───────┘──5────→┘

  dist: A=0, B=2, C=4, D=3
  path: A→B→D
```

**Problems:** Network Delay Time, Cheapest Flights Within K Stops, Swim in Rising Water, Path with Maximum Probability

### Pattern 17.2: Bellman-Ford

```
dist = [infinity] * n
dist[source] = 0

for i in range(n - 1):           // relax n-1 times
    for u, v, w in all_edges:
        if dist[u] + w < dist[v]:
            dist[v] = dist[u] + w

// Detect negative cycle: one more relaxation
for u, v, w in all_edges:
    if dist[u] + w < dist[v]:
        // NEGATIVE CYCLE EXISTS
```

### Pattern 17.3: Floyd-Warshall (All Pairs)

```
dist[i][j] = weight(i, j) or infinity
for k in range(n):              // intermediate vertex
    for i in range(n):
        for j in range(n):
            dist[i][j] = min(dist[i][j], dist[i][k] + dist[k][j])
```

### Pattern 17.4: 0-1 BFS (Deque-based)

**Signal:** Edge weights are only 0 or 1.

```
Use deque instead of priority queue:
  Weight 0 edge: push to FRONT
  Weight 1 edge: push to BACK
O(V + E) instead of O((V+E) log V)
```

---

## 18. MINIMUM SPANNING TREE

### Pattern 18.1: Kruskal's (Sort Edges + Union-Find)

```
Sort all edges by weight
uf = UnionFind(n)
mst = []
for edge in sorted_edges:
    if uf.union(edge.u, edge.v):    // different components
        mst.add(edge)
        if len(mst) == n - 1: break
```

### Pattern 18.2: Prim's (Grow from a Vertex)

```
visited = {0}
pq = [(weight, neighbor) for neighbor of vertex 0]
mstCost = 0

while pq and len(visited) < n:
    weight, u = heappop(pq)
    if u in visited: continue
    visited.add(u)
    mstCost += weight
    for v, w in graph[u]:
        if v not in visited:
            heappush(pq, (w, v))
```

**When to use which:**
- Kruskal's: sparse graphs (E ~ V), edges already available
- Prim's: dense graphs (E ~ V²), adjacency list

**Problems:** Min Cost to Connect All Points, Connecting Cities with Minimum Cost

---

## 19. STRING MATCHING

### Pattern 19.1: KMP (Knuth-Morris-Pratt)

**Signal:** Find pattern in text in O(n + m).

```
Build LPS (Longest Proper Prefix that is also Suffix) array:
  lps[0] = 0, len = 0, i = 1
  while i < m:
      if pattern[i] == pattern[len]:
          len++; lps[i] = len; i++
      else:
          if len > 0: len = lps[len - 1]   // don't increment i
          else: lps[i] = 0; i++

Search:
  i = 0, j = 0   // i for text, j for pattern
  while i < n:
      if text[i] == pattern[j]: i++; j++
      if j == m: found at i - j; j = lps[j - 1]
      elif i < n and text[i] != pattern[j]:
          if j > 0: j = lps[j - 1]
          else: i++
```

### Pattern 19.2: Rabin-Karp (Rolling Hash)

```
hash = sum(s[i] * base^(m-1-i)) mod prime

Rolling:
  hash = (hash - s[i] * base^(m-1)) * base + s[i + m]

Use for: multiple pattern search, longest duplicate substring
```

### Pattern 19.3: Z-Algorithm

```
Z[i] = length of longest substring starting at i that matches prefix of string

Application: concatenate pattern + "$" + text
  Z values >= len(pattern) indicate match positions
```

---

## 20. GAME THEORY

### Pattern 20.1: Minimax

**Signal:** Two players, optimal play, win/lose or maximize score difference.

```
def minimax(state, isMaximizing):
    if terminal(state): return evaluate(state)
    if isMaximizing:
        best = -infinity
        for move in possibleMoves(state):
            best = max(best, minimax(apply(state, move), false))
        return best
    else:
        best = +infinity
        for move in possibleMoves(state):
            best = min(best, minimax(apply(state, move), true))
        return best
```

### Pattern 20.2: DP Game (Stone Game)

```
dp[i][j] = maximum score difference (current player - opponent)
           for subarray piles[i..j]

dp[i][j] = max(
    piles[i] - dp[i+1][j],     // take left
    piles[j] - dp[i][j-1]      // take right
)

First player wins if dp[0][n-1] > 0
```

### Pattern 20.3: Nim Game / Sprague-Grundy

```
Nim: XOR all pile sizes. If XOR = 0, second player wins. Else first player wins.

Sprague-Grundy: compute Grundy number for each game state
  g(state) = mex({g(state') for all moves state → state'})
  mex = minimum excludant (smallest non-negative integer not in set)
  
  Combined game: XOR Grundy numbers of independent sub-games
```

---

## 21. DESIGN PATTERNS

### Pattern 21.1: LRU Cache (HashMap + Doubly Linked List)

```
Structure:
  HashMap<key, DLLNode> → O(1) lookup
  Doubly Linked List → O(1) insertion/deletion, maintains order

  HEAD ↔ [MRU] ↔ [..] ↔ [..] ↔ [LRU] ↔ TAIL

get(key):
    if key not in map: return -1
    node = map[key]
    moveToFront(node)          // mark as recently used
    return node.value

put(key, value):
    if key in map: update value, moveToFront
    else:
        if full: remove TAIL.prev (LRU), delete from map
        create new node, add to front, put in map
```

### Pattern 21.2: LFU Cache

```
HashMap<key, Node>
HashMap<freq, DoublyLinkedList>  // each freq has its own DLL
minFreq tracker

get: increase freq, move node to next freq's DLL
put: if full, evict from minFreq's DLL (tail = LRU among least frequent)
     add with freq=1, set minFreq=1
```

### Pattern 21.3: Design Twitter / News Feed

```
Components:
  - User → Set<followees>
  - User → List<Tweet> (with timestamp)
  - getFeed: merge k sorted lists (user + followees' tweets) using heap
```

### Pattern 21.4: Rate Limiter

```
Token Bucket:
  tokens += elapsed * rate
  tokens = min(tokens, bucketSize)
  if tokens >= 1: allow, tokens--
  else: reject

Sliding Window Log:
  Store timestamps of requests
  Remove timestamps older than window
  If count < limit: allow
  else: reject

Sliding Window Counter:
  curr_count + prev_count * overlap_percentage
```

### Pattern 21.5: Consistent Hashing (for System Design)

```
Ring of hash space [0, 2^32)
Place N virtual nodes per server on ring
To find server for key:
    hash(key) → find next server clockwise

Benefits: only K/N keys need remapping when server added/removed
```

---

## 22. CONCURRENCY PATTERNS

### Pattern 22.1: Producer-Consumer (Bounded Buffer)

```java
class BoundedQueue<T> {
    Queue<T> queue;
    int capacity;
    Lock lock = new ReentrantLock();
    Condition notFull = lock.newCondition();
    Condition notEmpty = lock.newCondition();

    void put(T item) {
        lock.lock();
        while (queue.size() == capacity) notFull.await();
        queue.add(item);
        notEmpty.signal();
        lock.unlock();
    }

    T take() {
        lock.lock();
        while (queue.isEmpty()) notEmpty.await();
        T item = queue.poll();
        notFull.signal();
        lock.unlock();
        return item;
    }
}
```

### Pattern 22.2: Read-Write Lock

```
Multiple readers OR single writer (never both)

readLock:  if no writer active/waiting → allow concurrent reads
writeLock: exclusive access, wait for all readers to finish
```

### Pattern 22.3: Thread-Safe Singleton (Double-Checked Locking)

```java
class Singleton {
    private static volatile Singleton instance;

    static Singleton getInstance() {
        if (instance == null) {
            synchronized (Singleton.class) {
                if (instance == null) {
                    instance = new Singleton();
                }
            }
        }
        return instance;
    }
}
```

### Pattern 22.4: Ordering / Sequencing

```
Print in Order: CountDownLatch or Semaphore
  latch1, latch2 (initialized to 0)
  Thread 1: print("first"); latch1.countDown()
  Thread 2: latch1.await(); print("second"); latch2.countDown()
  Thread 3: latch2.await(); print("third")

Alternating Print: synchronized + condition variable with turn tracking
```

### Pattern 22.5: Dining Philosophers (Deadlock Prevention)

```
Strategies:
1. Resource ordering: always pick lower-numbered fork first
2. Arbitrator: mutex to allow only 4 philosophers to try simultaneously
3. Chandy/Misra: message-passing with dirty/clean forks
```

---

## 23. ADVANCED PATTERNS

### Pattern 23.1: Sweep Line

**Signal:** Intervals on a line, rectangles, meeting room counting.

```
Events:
  for [start, end] in intervals:
      events.add((start, +1))    // opening
      events.add((end, -1))      // closing

Sort events by position (break ties: close before open, or vice versa)
Sweep through, maintaining active count:
  active = 0
  for pos, delta in events:
      active += delta
      maxActive = max(maxActive, active)
```

**Problems:** Skyline Problem, Meeting Rooms II, Number of Airplanes in the Sky

### Pattern 23.2: Reservoir Sampling

**Signal:** Random sample from unknown-size stream.

```
Choose k items from stream of unknown length n:
  result = first k items
  for i from k to n-1:
      j = random(0, i)
      if j < k: result[j] = stream[i]

Each item has exactly k/n probability of being selected.
```

### Pattern 23.3: Rolling Hash (Rabin-Karp Applications)

```
hash(s[i..i+m-1]) = s[i]*p^(m-1) + s[i+1]*p^(m-2) + ... + s[i+m-1]

Rolling update:
  hash = (hash - s[i] * p^(m-1)) * p + s[i+m]

Applications:
  - Longest duplicate substring (binary search on length + rolling hash)
  - Repeated DNA sequences
  - String matching
```

### Pattern 23.4: Euler Path / Circuit

```
Hierholzer's Algorithm:
  Start at any vertex (circuit) or odd-degree vertex (path)
  stack = [start]
  circuit = []
  while stack:
      v = stack[-1]
      if graph[v] has edges:
          u = graph[v].pop()  // remove edge
          stack.append(u)
      else:
          circuit.append(stack.pop())
  return circuit.reversed()
```

**Problems:** Reconstruct Itinerary

### Pattern 23.5: Strongly Connected Components (Tarjan's)

```
index = 0, stack = []
def tarjan(u):
    disc[u] = low[u] = index++
    stack.append(u); onStack[u] = true

    for v in graph[u]:
        if disc[v] == -1:
            tarjan(v)
            low[u] = min(low[u], low[v])
        elif onStack[v]:
            low[u] = min(low[u], disc[v])

    if low[u] == disc[u]:   // u is root of SCC
        component = []
        while true:
            w = stack.pop(); onStack[w] = false
            component.add(w)
            if w == u: break
        SCCs.add(component)
```

### Pattern 23.6: Articulation Points and Bridges

```
Bridge: edge (u,v) where low[v] > disc[u]
  (no back edge from v's subtree reaches above u)

Articulation Point: vertex u where:
  - u is root and has 2+ DFS children, OR
  - u is not root and has child v with low[v] >= disc[u]
```

---

## MASTER CHEAT SHEET

### Problem Signal → Pattern Mapping

| Signal in Problem | Pattern to Apply |
|---|---|
| "Sorted array, find pair" | Two Pointers (opposite ends) |
| "Longest/shortest subarray with constraint" | Sliding Window |
| "Minimum/maximum that satisfies condition" | Binary Search on Answer |
| "Count ways / min cost" | DP |
| "Can you reach / is it possible" | BFS/DFS or Greedy |
| "Generate all valid ___" | Backtracking |
| "Shortest path" | BFS (unweighted) / Dijkstra (weighted) |
| "Connected / components" | Union-Find or DFS |
| "Order of dependencies" | Topological Sort |
| "Next greater/smaller" | Monotonic Stack |
| "Kth largest / top K" | Heap or Quick Select |
| "Prefix search / autocomplete" | Trie |
| "Range query + update" | Segment Tree / BIT |
| "Intervals overlap/merge" | Sort + Sweep Line |
| "Stream of data" | Heap / Reservoir Sampling |
| "Game, two players" | Minimax / DP Game Theory |
| "Design a class with O(1) ops" | HashMap + LinkedList combo |

### Complexity Quick Reference

| Algorithm | Time | Space |
|-----------|------|-------|
| Binary Search | O(log n) | O(1) |
| Two Pointers | O(n) | O(1) |
| Sliding Window | O(n) | O(k) |
| DFS/BFS | O(V + E) | O(V) |
| Dijkstra | O((V+E) log V) | O(V) |
| Bellman-Ford | O(VE) | O(V) |
| Floyd-Warshall | O(V³) | O(V²) |
| Topological Sort | O(V + E) | O(V) |
| Union-Find | O(α(n)) ≈ O(1) | O(n) |
| Segment Tree | O(log n) query/update | O(n) |
| Trie | O(m) per operation | O(alphabet * m * n) |
| KMP | O(n + m) | O(m) |
| Kruskal MST | O(E log E) | O(V) |
| Quick Select | O(n) average | O(1) |
| Merge Sort | O(n log n) | O(n) |

### DP Pattern Recognition Quick Reference

| Problem Type | DP Pattern | State |
|---|---|---|
| Reach end in min steps | Linear DP | dp[i] = min steps to i |
| Rob houses, can't take adjacent | Skip/Take | dp[i] = max(skip, take) |
| Coin change / denominations | Unbounded Knapsack | dp[amount] |
| Subset with target sum | 0/1 Knapsack | dp[i][sum] |
| Compare two strings | 2D String DP | dp[i][j] for prefixes |
| Grid traversal | Grid DP | dp[i][j] |
| Split array optimally | Interval DP | dp[i][j] for range |
| Stock trading | State Machine | dp[day][holding/not][transactions] |
| Tree optimization | Tree DP | dfs returns (value_up, value_with_node) |
| Small set, track used | Bitmask DP | dp[mask] |

---

## VISUAL PATTERN DIAGRAMS

### Two Pointers vs Sliding Window vs Prefix Sum

```
TWO POINTERS (sorted):
  [1, 2, 3, 4, 5, 6, 7, 8, 9]
   ↑                          ↑
  left                      right
  Move based on comparison with target

SLIDING WINDOW (contiguous):
  [a, b, c, d, e, f, g, h, i]
      ├────window────┤
      left          right
  Expand right, shrink left

PREFIX SUM (any subarray sum):
  prefix: [0, 1, 3, 6, 10, 15, 21, 28, 36, 45]
                 ↑               ↑
              sum(2..5) = pre[6] - pre[2] = 21 - 3 = 18
```

### Graph Traversal Comparison

```
BFS (Level by Level):              DFS (Deep First):
     1                                  1
    / \                                / \
   2   3        Level 0: {1}          2   5
  / \   \       Level 1: {2,3}      / \    \
 4   5   6     Level 2: {4,5,6}   3   4    6

Visit: 1,2,3,4,5,6               Visit: 1,2,4,5,3,6
Use: shortest path                Use: explore all, cycle detect
```

### DP State Transition Diagram (Stock Trading)

```
                    buy
   ┌──────────────────────────────┐
   │                              │
   ▼          sell                │
┌──────┐  ─────────→  ┌────────┐ │
│ HOLD │               │  SOLD  │ │
└──────┘  ←─────────  └────────┘ │
   │          buy          │      │
   │                       │ cooldown
   │    hold (wait)        ▼      │
   │                  ┌────────┐  │
   └──────────────→   │  REST  │──┘
                      └────────┘
```

### Union-Find Operations

```
Initial:  {0} {1} {2} {3} {4}

union(0,1):  {0,1} {2} {3} {4}
union(2,3):  {0,1} {2,3} {4}
union(1,3):  {0,1,2,3} {4}

find(2) → follows parent pointers → root = 0
Path compression: 2→0 (shortcut)

     0              0
    / \    →      / | \ \
   1   2         1  2  3  (flat!)
       |
       3
```

---

## INTERVIEW EXECUTION FRAMEWORK

### Step 1: Clarify (2 min)
- Input size, constraints, edge cases
- Sorted? Negative numbers? Duplicates?
- Return type: count, boolean, actual elements?

### Step 2: Identify Pattern (1 min)
- Use the signal table above
- State the pattern explicitly: "This is a sliding window problem because..."

### Step 3: Approach (3 min)
- Describe algorithm at high level
- State complexity before coding
- Mention trade-offs if multiple approaches exist

### Step 4: Code (15 min)
- Write clean, template-based code
- Name variables clearly
- Handle edge cases inline

### Step 5: Verify (3 min)
- Trace through example
- Check edge cases: empty, single element, all same
- Confirm complexity matches what you stated

---

*End of Master Guide*
