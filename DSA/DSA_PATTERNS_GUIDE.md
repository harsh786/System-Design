# DSA Interview Patterns Guide - Part 1: Core Data Structures

> Review this the night before your interview. Patterns, not problems.

---

## 1. Arrays

### 1.1 Kadane's Algorithm (Maximum Subarray)

**When to Use:** Find maximum/minimum sum contiguous subarray.

```
Template:
  maxSum = curSum = nums[0]
  for i = 1 to n-1:
      curSum = max(nums[i], curSum + nums[i])  // extend or restart
      maxSum = max(maxSum, curSum)
  return maxSum
```

```
Array:  [-2, 1, -3, 4, -1, 2, 1, -5, 4]
curSum:  -2  1  -2  4   3  5  6   1  5
                    ^------------^
                    max subarray = 6
```

**Complexity:** O(n) time, O(1) space
**Problems:** Problem05_MaximumSubarray, Problem06_MaximumProductSubarray

---

### 1.2 Prefix Sum / Difference Array

**When to Use:** Range sum queries, subarray sum equals K, or bulk range updates.

```
Prefix Sum:
  pre[0] = 0
  pre[i] = pre[i-1] + nums[i-1]
  sum(l..r) = pre[r+1] - pre[l]

Subarray Sum = K (with HashMap):
  map = {0: 1}, count = 0
  runningSum = 0
  for num in nums:
      runningSum += num
      count += map.get(runningSum - k, 0)
      map[runningSum] += 1
```

```
nums:    [1, 2, 3, 4, 5]
prefix:  [0, 1, 3, 6, 10, 15]
              |        |
         sum(1..3) = pre[4] - pre[1] = 10 - 1 = 9
```

**Complexity:** O(n) build, O(1) query, O(1) space for difference array
**Problems:** Problem14_SubarraySumEqualsK, Problem04_ProductOfArrayExceptSelf

---

### 1.3 Dutch National Flag (3-Way Partition)

**When to Use:** Sort array of 3 distinct values in-place, or partition around pivot.

```
lo = 0, mid = 0, hi = n-1
while mid <= hi:
    if arr[mid] == 0: swap(lo, mid); lo++; mid++
    elif arr[mid] == 1: mid++
    else:              swap(mid, hi); hi--
```

```
[2, 0, 1, 2, 0, 1]
 ^lo,mid         ^hi
After: [0, 0, 1, 1, 2, 2]
```

**Complexity:** O(n) time, O(1) space
**Problems:** Problem13_SortColors

---

### 1.4 Rotate / Reverse Tricks

**When to Use:** Rotate array by k positions, reverse segments in-place.

```
Rotate right by k:
  k = k % n
  reverse(0, n-1)      // reverse entire array
  reverse(0, k-1)      // reverse first k
  reverse(k, n-1)      // reverse rest

[1,2,3,4,5,6,7] k=3
-> [7,6,5,4,3,2,1]    // full reverse
-> [5,6,7,4,3,2,1]    // reverse 0..2
-> [5,6,7,1,2,3,4]    // reverse 3..6
```

**Complexity:** O(n) time, O(1) space
**Problems:** Problem15_RotateArray

---

### 1.5 Boyer-Moore Voting Algorithm

**When to Use:** Find majority element (appears > n/2 times) in O(1) space.

```
candidate = null, count = 0
for num in nums:
    if count == 0: candidate = num
    count += (1 if num == candidate else -1)
return candidate
```

**Intuition:** Majority element survives all cancellations.

**Complexity:** O(n) time, O(1) space
**Problems:** Problem21_MajorityElement

---

### 1.6 In-Place Write Pointer

**When to Use:** Remove/move elements in-place, dedup sorted array.

```
write = 0
for read in range(n):
    if condition(nums[read]):
        nums[write] = nums[read]
        write++
return write  // new length
```

```
Move zeroes: [0,1,0,3,12]
read -->           write stays behind
Result: [1,3,12,0,0]
```

**Complexity:** O(n) time, O(1) space
**Problems:** Problem23_MoveZeroes, Problem17_FirstMissingPositive

---

### 1.7 Interval Merge / Overlap

**When to Use:** Merge overlapping intervals, insert interval, find conflicts.

```
Sort by start time
merged = [intervals[0]]
for i = 1 to n-1:
    if intervals[i].start <= merged.last.end:
        merged.last.end = max(merged.last.end, intervals[i].end)
    else:
        merged.append(intervals[i])
```

```
Input:  [1,3] [2,6] [8,10] [15,18]
         |-----|
         merged:[1,6]       [8,10]  [15,18]
```

**Complexity:** O(n log n) time, O(n) space
**Problems:** Problem12_MergeIntervals, Problem26_InsertInterval, Problem27_NonOverlappingIntervals

---

### 1.8 Two-Pass / Left-Right Product

**When to Use:** Compute something depending on both left and right context without division.

```
Product Except Self:
  left[i]  = product of nums[0..i-1]
  right[i] = product of nums[i+1..n-1]
  result[i] = left[i] * right[i]

O(1) space variant: use output array for left pass, variable for right pass.
```

**Complexity:** O(n) time, O(1) extra space
**Problems:** Problem04_ProductOfArrayExceptSelf, Problem16_TrappingRainWater

---

## 2. Strings

### 2.1 Character Frequency Counting (Fixed Array)

**When to Use:** Anagram checks, character-based comparisons, frequency constraints.

```
int[] freq = new int[26];
for (char c : s.toCharArray()) freq[c - 'a']++;

// Compare two frequency arrays for anagram check
Arrays.equals(freq1, freq2)
```

**Why not HashMap?** Array[26] is faster (no hashing) and uses fixed space.

**Complexity:** O(n) time, O(1) space (26 is constant)
**Problems:** Problem01_ValidAnagram, Problem02_GroupAnagrams

---

### 2.2 Palindrome: Expand from Center

**When to Use:** Find longest palindromic substring, count palindromes.

```
for each center i (and i,i+1 for even):
    l = i, r = i  (or i, i+1)
    while l >= 0 and r < n and s[l] == s[r]:
        update longest
        l--, r++
```

```
  "babad"
   ^ expand from index 1: "aba" -> palindrome
     ^ expand from index 2: "bab" -> palindrome
```

**Complexity:** O(n^2) time, O(1) space
**Problems:** Problem08_LongestPalindromicSubstring, Problem06_ValidPalindrome

---

### 2.3 Anagram Grouping (Sorted Key / Frequency Key)

**When to Use:** Group strings that are permutations of each other.

```
Map<String, List<String>> groups
for word in words:
    key = sort(word)       // "eat" -> "aet"
    groups[key].add(word)

Alt key: frequency string "a2b1c0..." for O(n) vs O(n log n)
```

**Complexity:** O(n * k log k) with sorting, O(n * k) with freq key
**Problems:** Problem02_GroupAnagrams

---

### 2.4 Encode / Decode Strings

**When to Use:** Serialize list of strings into single string and back.

```
Encode: for each s -> len + "#" + s
  ["hello","world"] -> "5#hello5#world"

Decode: read number until '#', extract that many chars, repeat.
```

**Complexity:** O(n) time
**Problems:** Problem12_EncodeDecodeStrings

---

### 2.5 String to Integer (Parsing)

**When to Use:** Implement atoi, handle edge cases systematically.

```
Checklist:
  1. Skip whitespace
  2. Handle sign (+/-)
  3. Read digits, build number: num = num * 10 + digit
  4. Clamp to [INT_MIN, INT_MAX] on overflow
  5. Stop on non-digit
```

**Problems:** Problem13_StringToInteger

---

### 2.6 Decode Nested Strings

**When to Use:** Nested encoded patterns like `3[a2[c]]`.

```
Use stack of (currentString, multiplier):
  on '[': push current state, reset
  on ']': pop, repeat current string, append to popped
  on digit: build multiplier
  on letter: append to current
```

**Complexity:** O(output length) time
**Problems:** Problem11_DecodeString

---

### 2.7 Substring Search (KMP / Rabin-Karp)

**When to Use:** Find pattern in text efficiently.

```
KMP core: build failure/LPS array
  lps[i] = length of longest proper prefix of pattern[0..i]
           that is also a suffix

Rabin-Karp: rolling hash
  hash = (hash - s[i-1] * p^(m-1)) * p + s[i+m-1]
```

**Complexity:** O(n + m) for KMP, O(n + m) avg for Rabin-Karp
**Problems:** Problem10_StrStr

---

## 3. Hash Table

### 3.1 Two Sum / Complement Lookup

**When to Use:** Find pair summing to target, or any complement-based search.

```
map = {}
for i, num in enumerate(nums):
    complement = target - num
    if complement in map: return [map[complement], i]
    map[num] = i
```

**Key insight:** One pass. Store what you've seen, look up what you need.

**Complexity:** O(n) time, O(n) space
**Problems:** Problem01_TwoSum

---

### 3.2 Frequency Counting

**When to Use:** Top K frequent, first unique, character counts.

```
freq = Counter(nums)
// then sort by frequency, use heap, or bucket sort

Bucket sort for Top K (O(n)):
  buckets[count] = [elements with that count]
  iterate buckets from high to low, collect K elements
```

**Complexity:** O(n) with bucket sort, O(n log k) with heap
**Problems:** Problem05_TopKFrequentElements, Problem16_FirstUniqueCharacter

---

### 3.3 Group by Key

**When to Use:** Group items sharing a property (anagrams, isomorphic pattern).

```
map = defaultdict(list)
for item in items:
    key = computeKey(item)  // sorted string, pattern code, etc.
    map[key].append(item)

Pattern encoding for isomorphic:
  "egg" -> "0.1.1"   "add" -> "0.1.1"  (same pattern)
```

**Problems:** Problem02_GroupAnagrams, Problem08_IsomorphicStrings, Problem09_WordPattern

---

### 3.4 Prefix Sum + HashMap (Subarray Sum = K)

**When to Use:** Count/find subarrays with exact sum K, sum divisible by K, equal 0s and 1s.

```
map = {0: 1}     // empty prefix
runningSum = 0, count = 0
for num in nums:
    runningSum += num
    count += map.get(runningSum - k, 0)
    map[runningSum] = map.get(runningSum, 0) + 1
```

```
nums: [1, 1, 1], k = 2
pre:   1  2  3
at pre=2: map has {0:1, 1:1} -> 2-2=0 exists -> count++
at pre=3: map has {0:1, 1:1, 2:1} -> 3-2=1 exists -> count++
count = 2 -> subarrays [1,1] at positions 0-1 and 1-2
```

**Complexity:** O(n) time, O(n) space
**Problems:** Problem07_SubarraySumEqualsK, Problem28_ContiguousArray

---

### 3.5 Index Mapping (First/Last Occurrence)

**When to Use:** Track positions, contains duplicate within k distance.

```
map[value] = last index seen
for i, num in enumerate(nums):
    if num in map and i - map[num] <= k: return true
    map[num] = i
```

**Problems:** Problem06_ContainsDuplicateII

---

### 3.6 Hash as Visited Set

**When to Use:** Cycle detection in sequences, happy number.

```
seen = set()
while x not in seen:
    seen.add(x)
    x = transform(x)
// x is the cycle entry point
```

**Alt:** Floyd's for O(1) space (see Linked List section).

**Problems:** Problem14_HappyNumber, Problem10_LongestConsecutiveSequence

---

## 4. Linked List

### 4.1 Fast / Slow Pointer (Floyd's)

**When to Use:** Detect cycle, find cycle start, find middle node.

```
Cycle detection:
  slow = fast = head
  while fast and fast.next:
      slow = slow.next
      fast = fast.next.next
      if slow == fast: return true  // cycle!

Find cycle start:
  After detection, reset slow = head
  while slow != fast:
      slow = slow.next
      fast = fast.next
  return slow  // cycle entry
```

```
  1 -> 2 -> 3 -> 4 -> 5
                  ^    |
                  |----+  (cycle)
  slow: 1,2,3,4,5,3,4
  fast: 1,3,5,4,3,5,4
  meet at node with value depends on cycle
```

**Complexity:** O(n) time, O(1) space
**Problems:** Problem03_LinkedListCycle, Problem04_LinkedListCycleII, Problem25_MiddleOfLinkedList

---

### 4.2 Reverse Linked List

**When to Use:** Reverse entire list or subsection, palindrome check.

```
Iterative:
  prev = null, curr = head
  while curr:
      next = curr.next
      curr.next = prev
      prev = curr
      curr = next
  return prev

  null <- 1 <- 2 <- 3    (prev = 3 = new head)
```

```
Recursive:
  reverse(node):
      if !node or !node.next: return node
      newHead = reverse(node.next)
      node.next.next = node
      node.next = null
      return newHead
```

**Complexity:** O(n) time, O(1) iterative / O(n) recursive space
**Problems:** Problem01_ReverseLinkedList, Problem26_ReverseLinkedListII, Problem16_ReverseNodesInKGroup

---

### 4.3 Merge Two Sorted Lists

**When to Use:** Merge sorted lists, base case for merge k lists.

```
dummy = ListNode(0)
tail = dummy
while l1 and l2:
    if l1.val <= l2.val:
        tail.next = l1; l1 = l1.next
    else:
        tail.next = l2; l2 = l2.next
    tail = tail.next
tail.next = l1 or l2
return dummy.next
```

**Complexity:** O(n + m) time, O(1) space
**Problems:** Problem02_MergeTwoSortedLists, Problem09_MergeKSortedLists

---

### 4.4 Dummy Head Technique

**When to Use:** When head node might change (deletion, insertion at front, partition).

```
dummy = ListNode(0)
dummy.next = head
// ... operate with prev starting at dummy
return dummy.next
```

**Why:** Eliminates edge cases for head modification. Use it by default.

**Problems:** Problem05_RemoveNthNodeFromEnd, Problem17_RemoveDuplicatesFromSortedList, Problem19_PartitionList

---

### 4.5 Nth from End (Two Pointers)

**When to Use:** Remove/find nth node from end without knowing length.

```
fast = head
for i in range(n): fast = fast.next  // advance fast by n
slow = head
while fast.next:   // (use dummy for removal)
    slow = slow.next
    fast = fast.next
// slow is at (n+1)th from end -> slow.next is target
```

**Complexity:** O(n) time, O(1) space, single pass
**Problems:** Problem05_RemoveNthNodeFromEnd

---

### 4.6 Detect Intersection

**When to Use:** Find node where two lists converge.

```
a, b = headA, headB
while a != b:
    a = a.next if a else headB
    b = b.next if b else headA
return a  // intersection or null

// Works because both traverse len(A) + len(B) total
```

**Complexity:** O(n + m) time, O(1) space
**Problems:** Problem11_IntersectionOfTwoLinkedLists

---

### 4.7 Reorder / Rearrange

**When to Use:** Interleave, odd-even split, reorder L0->Ln->L1->Ln-1...

```
Reorder List:
  1. Find middle (fast/slow)
  2. Reverse second half
  3. Merge/interleave two halves

  1->2->3->4->5  =>  1->5->2->4->3
```

**Problems:** Problem06_ReorderList, Problem23_OddEvenLinkedList, Problem10_PalindromeLinkedList

---

## 5. Stack

### 5.1 Bracket Matching / Validation

**When to Use:** Valid parentheses, matching delimiters.

```
map = {')':'(', ']':'[', '}':'{'}
stack = []
for c in s:
    if c in map:
        if not stack or stack[-1] != map[c]: return false
        stack.pop()
    else:
        stack.push(c)
return stack.isEmpty()
```

**Complexity:** O(n) time, O(n) space
**Problems:** Problem01_ValidParentheses, Problem20_LongestValidParentheses

---

### 5.2 Monotonic Stack (Next Greater / Smaller)

**When to Use:** Next greater element, daily temperatures, largest rectangle, stock span.

```
Next Greater Element:
  result = [-1] * n
  stack = []  // stores indices, maintains decreasing values
  for i in range(n):
      while stack and nums[i] > nums[stack[-1]]:
          result[stack.pop()] = nums[i]
      stack.push(i)
```

```
nums:   [2, 1, 2, 4, 3]
stack:  [0]           -> push 2
        [0,1]         -> push 1  (1 < 2, no pop)
        [0,2]         -> 2 >= 1, pop 1->ans=2; 2 >= 2, pop 0->ans=2; push 2
        [3]           -> 4 > 2, pop->ans=4; push 4
        [3,4]         -> push 3
result: [2, 2, 4, -1, -1]
```

**Complexity:** O(n) time (each element pushed/popped once), O(n) space
**Problems:** Problem04_DailyTemperatures, Problem14_NextGreaterElementI, Problem06_LargestRectangleInHistogram, Problem16_OnlineStockSpan

---

### 5.3 Expression Evaluation (Calculator)

**When to Use:** Parse and evaluate arithmetic expressions with +, -, *, /, parentheses.

```
Basic Calculator II (no parens):
  stack = [], num = 0, op = '+'
  for c in s + '+':
      if c.isdigit(): num = num * 10 + int(c)
      elif c is operator:
          if op == '+': stack.push(num)
          elif op == '-': stack.push(-num)
          elif op == '*': stack.push(stack.pop() * num)
          elif op == '/': stack.push(trunc(stack.pop() / num))
          op = c; num = 0
  return sum(stack)

With parens: recurse or use second stack for context saving.
```

**Problems:** Problem09_BasicCalculator, Problem10_BasicCalculatorII, Problem26_BasicCalculatorIII

---

### 5.4 Min Stack (Auxiliary Stack)

**When to Use:** Stack with O(1) getMin().

```
Two stacks: main + minStack
push(x):
    main.push(x)
    minStack.push(min(x, minStack.peek()))  // or push only when x <= current min
pop():
    main.pop()
    minStack.pop()
getMin(): return minStack.peek()
```

**Complexity:** O(1) all operations
**Problems:** Problem02_MinStack

---

### 5.5 Stack for Undo / Simulation

**When to Use:** Backspace string compare, asteroid collision, baseball game scoring.

```
Asteroid Collision:
  stack = []
  for a in asteroids:
      while stack and a < 0 < stack[-1]:
          if stack[-1] < -a: stack.pop(); continue
          elif stack[-1] == -a: stack.pop()
          break
      else:
          stack.push(a)
```

**Problems:** Problem08_AsteroidCollision, Problem27_BaseballGame, Problem28_CrawlerLogFolder

---

### 5.6 Remove K Digits / Monotonic Build

**When to Use:** Build smallest/largest number by removing digits, remove duplicates maintaining order.

```
stack = []
for digit in num:
    while k > 0 and stack and stack[-1] > digit:
        stack.pop(); k--
    stack.push(digit)
// remove remaining k from end, strip leading zeros
```

**Problems:** Problem18_RemoveKDigits

---

## 6. Queue

### 6.1 BFS Level-Order Traversal

**When to Use:** Shortest path in unweighted graph, level-by-level processing.

```
queue = deque([start])
visited = {start}
level = 0
while queue:
    for _ in range(len(queue)):    // process one level
        node = queue.popleft()
        for neighbor in adj[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    level++
```

**Key:** `for _ in range(len(queue))` processes exactly one level.

**Complexity:** O(V + E) time, O(V) space
**Problems:** Problem30_BinaryTreeLevelOrderTraversal, Problem08_RottingOranges, Problem15_WordLadder

---

### 6.2 Monotonic Deque (Sliding Window Maximum)

**When to Use:** Max/min in sliding window of size k.

```
deque = []  // stores indices, front = max
for i in range(n):
    while deque and deque[0] <= i - k:
        deque.popleft()                    // remove out-of-window
    while deque and nums[deque[-1]] <= nums[i]:
        deque.pop()                        // maintain decreasing
    deque.append(i)
    if i >= k - 1:
        result.append(nums[deque[0]])      // front is max
```

```
nums: [1,3,-1,-3,5,3,6,7], k=3
deque indices -> values at front
[1]->3  [1,2]->3  window: max=3
[1,2]->3  remove nothing, max=3 | [-1 added, 3 still front]
[4]->5 ...
```

**Complexity:** O(n) time, O(k) space
**Problems:** Problem07_SlidingWindowMaximum

---

### 6.3 Circular Queue

**When to Use:** Fixed-size buffer, producer-consumer.

```
class CircularQueue:
    front = 0, rear = -1, size = 0
    enqueue(x): rear = (rear + 1) % capacity; arr[rear] = x; size++
    dequeue():  val = arr[front]; front = (front + 1) % capacity; size--; return val
    isFull():   return size == capacity
    isEmpty():  return size == 0
```

**Problems:** Problem04_DesignCircularQueue, Problem05_DesignCircularDeque

---

### 6.4 Queue + Stack Interconversion

**When to Use:** Implement queue using stacks or vice versa.

```
Queue using 2 stacks:
  push: always push to stack1
  pop:  if stack2 empty, pour stack1 -> stack2
        pop from stack2

  Amortized O(1) per operation.
```

**Problems:** Problem01_ImplementQueueUsingStacks, Problem02_ImplementStackUsingQueues

---

### 6.5 Multi-Source BFS

**When to Use:** Propagation from multiple starting points (rotting oranges, walls and gates, 01 matrix).

```
queue = deque()
for all sources: queue.append(source)  // add ALL sources initially
// standard BFS from here
```

**Key insight:** Instead of BFS from each source separately, start with all sources in queue simultaneously.

**Complexity:** O(m * n) for grid problems
**Problems:** Problem08_RottingOranges, Problem09_WallsAndGates, Problem28_01Matrix

---

## 7. Heap / Priority Queue

### 7.1 Top K / Kth Largest

**When to Use:** Find K largest/smallest/most frequent elements.

```
Kth Largest - Min Heap of size K:
  heap = MinHeap()
  for num in nums:
      heap.push(num)
      if heap.size > k: heap.pop()
  return heap.peek()  // kth largest

Top K Frequent:
  1. Count frequencies
  2. Min-heap of size k by frequency, OR
  3. Bucket sort: bucket[freq] = [elements] -> O(n)
```

**Complexity:** O(n log k) with heap, O(n) with bucket sort/quickselect
**Problems:** Problem01_KthLargestElement, Problem02_TopKFrequentElements, Problem06_KClosestPointsToOrigin

---

### 7.2 Merge K Sorted Lists/Arrays

**When to Use:** Merge multiple sorted sequences.

```
heap = MinHeap()
for each list i: heap.push((list[i][0], i, 0))  // (val, list_idx, elem_idx)
while heap:
    val, li, ei = heap.pop()
    result.append(val)
    if ei + 1 < len(lists[li]):
        heap.push((lists[li][ei+1], li, ei+1))
```

**Complexity:** O(N log k) where N = total elements, k = number of lists
**Problems:** Problem04_MergeKSortedLists, Problem13_SmallestRangeCoveringKLists

---

### 7.3 Running Median (Two Heaps)

**When to Use:** Maintain median as elements stream in.

```
maxHeap (left half)    minHeap (right half)
  stores smaller half    stores larger half

addNum(x):
  maxHeap.push(x)
  minHeap.push(maxHeap.pop())     // balance: push to left, move max to right
  if minHeap.size > maxHeap.size:
      maxHeap.push(minHeap.pop()) // keep left >= right in size

median:
  if equal sizes: (maxHeap.peek() + minHeap.peek()) / 2
  else: maxHeap.peek()
```

```
Stream: 5, 2, 8
  maxHeap: [2,5]   minHeap: [8]
  median = maxHeap.peek() = 5   -- wait no...

  add 5: max=[5], min=[] -> rebalance -> max=[5], min=[]
  add 2: max=[2,5]->pop 5->min=[5], max=[2] -> sizes 1,1 ok
  add 8: max=[2,8]->pop 8->min=[5,8], max=[2] -> min bigger->pop 5->max=[2,5]
  median = 5 ✓
```

**Complexity:** O(log n) per insert, O(1) median query
**Problems:** Problem03_FindMedianFromDataStream, Problem15_SlidingWindowMedian

---

### 7.4 Greedy Scheduling with Heap

**When to Use:** Task scheduling, meeting rooms, CPU scheduling.

```
Meeting Rooms II (min rooms):
  Sort by start time
  minHeap of end times
  for each meeting:
      if heap.peek() <= meeting.start: heap.pop()  // room freed
      heap.push(meeting.end)
  return heap.size
```

**Complexity:** O(n log n)
**Problems:** Problem12_MeetingRoomsII, Problem05_TaskScheduler, Problem14_IPO

---

### 7.5 Lazy Deletion

**When to Use:** When removing specific elements from heap is needed but heap doesn't support efficient arbitrary removal.

```
// Instead of removing, mark as deleted in a separate map/set
// On pop, skip elements that are marked deleted
while heap and heap.peek() in deleted:
    deleted.remove(heap.pop())
```

**Complexity:** Amortized same as normal heap operations
**Problems:** Problem15_SlidingWindowMedian

---

## 8. Trees

### 8.1 DFS Traversals

**When to Use:** Almost every tree problem. Choose order based on need.

```
Preorder  (Root-L-R): process before children -> serialize, copy tree
Inorder   (L-Root-R): BST gives sorted order -> kth smallest
Postorder (L-R-Root): process after children -> delete, height, diameter

Iterative Inorder:
  stack = []
  curr = root
  while curr or stack:
      while curr:
          stack.push(curr)
          curr = curr.left
      curr = stack.pop()
      visit(curr)
      curr = curr.right
```

**Problems:** Problem05_ValidateBST, Problem15_KthSmallestInBST, Problem18_FlattenBinaryTreeToLinkedList

---

### 8.2 BFS Level-Order

**When to Use:** Level-by-level processing, right side view, zigzag.

```
queue = [root]
while queue:
    level = []
    for _ in range(len(queue)):
        node = queue.popleft()
        level.append(node.val)
        if node.left: queue.append(node.left)
        if node.right: queue.append(node.right)
    result.append(level)
```

**Problems:** Problem04_BinaryTreeLevelOrderTraversal, Problem25_BinaryTreeRightSideView, Problem26_ZigzagLevelOrderTraversal

---

### 8.3 Tree Construction from Traversals

**When to Use:** Build tree from preorder+inorder or postorder+inorder.

```
Preorder + Inorder:
  root = preorder[preIdx++]
  find root in inorder -> splits into left/right subtrees
  root.left  = build(inorder left portion)
  root.right = build(inorder right portion)

Optimization: use HashMap for inorder index lookup -> O(n) total
```

```
preorder: [3,9,20,15,7]    inorder: [9,3,15,20,7]
root = 3
inorder left of 3:  [9]     -> left subtree
inorder right of 3: [15,20,7] -> right subtree
```

**Complexity:** O(n) time with hashmap
**Problems:** Problem09_ConstructFromPreorderInorder

---

### 8.4 Path Sum Patterns

**When to Use:** Root-to-leaf sums, any-node path sums, max path sum.

```
Root-to-Leaf:
  dfs(node, remaining):
      if leaf and remaining == 0: found!
      dfs(node.left, remaining - node.val)
      dfs(node.right, remaining - node.val)

Max Path Sum (any path through node):
  dfs(node):
      if !node: return 0
      left = max(0, dfs(node.left))    // ignore negative paths
      right = max(0, dfs(node.right))
      maxSum = max(maxSum, left + right + node.val)  // path through node
      return max(left, right) + node.val             // return single branch
```

**Complexity:** O(n) time, O(h) space
**Problems:** Problem13_PathSum, Problem14_PathSumII, Problem10_BinaryTreeMaxPathSum

---

### 8.5 Lowest Common Ancestor (LCA)

**When to Use:** Find shared ancestor of two nodes.

```
BST LCA (use BST property):
  if p.val < node.val and q.val < node.val: go left
  elif p.val > node.val and q.val > node.val: go right
  else: return node  // split point

General BT LCA:
  lca(node, p, q):
      if !node or node == p or node == q: return node
      left = lca(node.left, p, q)
      right = lca(node.right, p, q)
      if left and right: return node    // p,q in different subtrees
      return left or right
```

**Complexity:** O(n) time general, O(h) for BST
**Problems:** Problem06_LowestCommonAncestor, Problem30_LCAofBST

---

### 8.6 Tree DP (Diameter, Max Path Sum)

**When to Use:** Optimization problems on tree structure where answer depends on subtree results.

```
Diameter = longest path between any two nodes (in edges)

dfs(node):
    if !node: return 0
    left = dfs(node.left)
    right = dfs(node.right)
    diameter = max(diameter, left + right)  // path through this node
    return max(left, right) + 1             // height to return

Pattern: at each node, combine left+right for answer, return single branch up.
```

**Problems:** Problem11_DiameterOfBinaryTree, Problem10_BinaryTreeMaxPathSum, Problem23_HouseRobberIII

---

### 8.7 Serialize / Deserialize

**When to Use:** Convert tree to string and back.

```
Preorder with nulls:
  serialize: "1,2,null,null,3,4,null,null,5,null,null"
  deserialize: read values, recursively build
      val = next()
      if val == "null": return null
      node = TreeNode(val)
      node.left = deserialize()
      node.right = deserialize()
      return node

BFS alternative: level-order with nulls (like LeetCode format)
```

**Problems:** Problem07_SerializeDeserializeBinaryTree

---

### 8.8 Morris Traversal (O(1) Space)

**When to Use:** Inorder traversal without stack/recursion.

```
curr = root
while curr:
    if !curr.left:
        visit(curr)
        curr = curr.right
    else:
        pred = curr.left
        while pred.right and pred.right != curr:
            pred = pred.right
        if !pred.right:              // first visit: thread
            pred.right = curr
            curr = curr.left
        else:                        // second visit: unthread
            pred.right = null
            visit(curr)
            curr = curr.right
```

**Complexity:** O(n) time, O(1) space -- modifies tree temporarily

---

### 8.9 Vertical / Boundary / Zigzag Traversal

**When to Use:** Non-standard traversal orders.

```
Vertical Order: BFS with column index
  map: col -> list of values
  queue: (node, col), root at col 0
  left child: col-1, right child: col+1
  sort by col, then row, then value

Zigzag: BFS, reverse alternate levels

Boundary: left boundary + leaves + right boundary (reversed)
```

**Problems:** Problem27_VerticalOrderTraversal, Problem26_ZigzagLevelOrderTraversal, Problem28_BoundaryOfBinaryTree

---

## 9. Trie

### 9.1 Basic Trie (Insert / Search / StartsWith)

**When to Use:** Prefix-based lookups, autocomplete, dictionary operations.

```
class TrieNode:
    children = new TrieNode[26]  // or HashMap for Unicode
    isEnd = false

insert(word):
    node = root
    for c in word:
        if !node.children[c]: node.children[c] = new TrieNode()
        node = node.children[c]
    node.isEnd = true

search(word): traverse, check isEnd at last char
startsWith(prefix): traverse, return true if all chars found
```

```
       root
      / | \
     a  b  c
     |  |
     p  a
     |  |
     p  d
     |
     (end)  -> "app"
```

**Complexity:** O(m) per operation where m = word length
**Problems:** Problem01_ImplementTrie, Problem07_SearchSuggestionsSystem, Problem15_DesignSearchAutocomplete

---

### 9.2 Word Search II (Trie + Backtracking)

**When to Use:** Find multiple words in a grid simultaneously.

```
Build trie from word list
for each cell in grid:
    dfs(i, j, trieNode):
        if trieNode has word: add to result
        mark cell visited
        for 4 directions:
            if in bounds and not visited and child exists:
                dfs(ni, nj, child)
        unmark cell

Optimization: remove word from trie after finding (prune)
```

**Complexity:** O(m*n * 4^L) worst case, trie prunes heavily in practice
**Problems:** Problem03_WordSearchII

---

### 9.3 XOR Trie (Maximum XOR Pair)

**When to Use:** Find max XOR of two numbers, XOR queries.

```
Build binary trie (MSB to LSB, 32 levels)
For max XOR with x:
    node = root
    for bit from 31 to 0:
        desired = opposite bit of x
        if node.children[desired] exists:
            node = node.children[desired]  // take opposite for max XOR
        else:
            node = node.children[1-desired]
```

**Complexity:** O(n * 32) = O(n) time
**Problems:** Problem09_MaximumXOR, Problem28_BinaryTrieMaxXOR, Problem29_BinaryTrieMinXORPair

---

### 9.4 Wildcard Search with '.'

**When to Use:** Search with wildcard characters.

```
search(word, node, idx):
    if idx == len(word): return node.isEnd
    if word[idx] == '.':
        for each non-null child:
            if search(word, child, idx+1): return true
    else:
        child = node.children[word[idx]]
        if child: return search(word, child, idx+1)
    return false
```

**Complexity:** O(26^m) worst case with all dots, typically much better
**Problems:** Problem02_AddAndSearchWords

---

### 9.5 Counting Prefixes

**When to Use:** Count words with given prefix, prefix scores.

```
class TrieNode:
    children, prefixCount = 0, wordCount = 0

insert(word):
    for c in word:
        node = node.children[c]
        node.prefixCount++    // every word passing through
    node.wordCount++

countPrefix(prefix): traverse, return node.prefixCount
```

**Problems:** Problem24_SumOfPrefixScores, Problem19_LongestWordWithAllPrefixes

---

## 10. Matrix

### 10.1 Spiral Traversal

**When to Use:** Read/write matrix in spiral order.

```
top, bottom, left, right = 0, m-1, 0, n-1
while top <= bottom and left <= right:
    for i in left..right:  result.add(matrix[top][i])     // →
    top++
    for i in top..bottom:  result.add(matrix[i][right])   // ↓
    right--
    if top <= bottom:
        for i in right..left (reverse): result.add(matrix[bottom][i])  // ←
        bottom--
    if left <= right:
        for i in bottom..top (reverse): result.add(matrix[i][left])    // ↑
        left++
```

**Complexity:** O(m*n) time, O(1) extra space
**Problems:** Problem02_SpiralMatrix

---

### 10.2 Rotate Matrix 90° (Transpose + Reverse)

**When to Use:** In-place rotation.

```
Clockwise 90°:
  1. Transpose (swap matrix[i][j] with matrix[j][i])
  2. Reverse each row

Counter-clockwise 90°:
  1. Transpose
  2. Reverse each column

180°: Reverse rows, then reverse each row
```

```
[1,2,3]   transpose   [1,4,7]   reverse rows   [7,4,1]
[4,5,6]   -------->   [2,5,8]   ------------>   [8,5,2]
[7,8,9]                [3,6,9]                   [9,6,3]
```

**Complexity:** O(n^2) time, O(1) space
**Problems:** Problem03_RotateImage

---

### 10.3 Staircase Search (Sorted Matrix)

**When to Use:** Search in matrix sorted row-wise and column-wise.

```
Start from top-right (or bottom-left):
  row = 0, col = n-1
  while row < m and col >= 0:
      if matrix[row][col] == target: return true
      elif matrix[row][col] > target: col--   // too big, go left
      else: row++                              // too small, go down
```

```
  [1,  4,  7, 11]
  [2,  5,  8, 12]    search 5: start at 11
  [3,  6,  9, 16]    11>5 -> 7>5 -> 4<5 -> 5 ✓
  [10,13, 14, 17]
```

**Complexity:** O(m + n) time, O(1) space
**Problems:** Problem05_SearchA2DMatrixII

For strictly sorted (row-major): treat as 1D, binary search O(log(m*n))
**Problems:** Problem04_SearchA2DMatrix

---

### 10.4 Island Problems (DFS/BFS Flood Fill)

**When to Use:** Count islands, max area, perimeter, surrounded regions.

```
count = 0
for i in range(m):
    for j in range(n):
        if grid[i][j] == '1':
            count++
            dfs(i, j)  // mark entire island as visited

dfs(i, j):
    if out of bounds or grid[i][j] != '1': return
    grid[i][j] = '0'  // mark visited (modify in-place)
    dfs(i±1, j); dfs(i, j±1)
```

**Complexity:** O(m*n) time, O(m*n) worst case stack space
**Problems:** Problem07_NumberOfIslands, Problem28_MaxAreaOfIsland, Problem12_SurroundedRegions, Problem11_PacificAtlanticWaterFlow, Problem22_IslandPerimeter

---

### 10.5 DP on Grids

**When to Use:** Count paths, min cost path, maximal square.

```
Unique Paths:
  dp[i][j] = dp[i-1][j] + dp[i][j-1]

Min Path Sum:
  dp[i][j] = grid[i][j] + min(dp[i-1][j], dp[i][j-1])

Maximal Square:
  dp[i][j] = min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1]) + 1
             if matrix[i][j] == '1'

Space optimization: use 1D array (previous row only)
```

**Complexity:** O(m*n) time, O(n) space with optimization
**Problems:** Problem15_UniquePaths, Problem16_MinimumPathSum, Problem08_MaximalSquare

---

### 10.6 Diagonal Traversal

**When to Use:** Process matrix diagonally.

```
Key insight: elements on same diagonal share same (i+j) or (i-j)

for d in range(m + n - 1):
    if d % 2 == 0: traverse upward   (row--, col++)
    else:          traverse downward  (row++, col--)

    Handle boundary adjustments for start position.
```

**Problems:** Problem18_DiagonalTraverse

---

### 10.7 Set Matrix Zeroes (Marking Pattern)

**When to Use:** Modify matrix based on conditions without extra space.

```
Use first row and first column as markers:
  1. Check if first row/col themselves need zeroing (save in booleans)
  2. For rest of matrix: if matrix[i][j]==0, set matrix[i][0]=0, matrix[0][j]=0
  3. Zero out cells based on markers
  4. Handle first row/col last
```

**Complexity:** O(m*n) time, O(1) space
**Problems:** Problem01_SetMatrixZeroes

---

## Quick Reference: Pattern Selection Cheat Sheet

| Signal | Pattern |
|--------|---------|
| Max/min subarray sum | Kadane's |
| Range sum query / subarray sum = K | Prefix Sum + HashMap |
| Sort 3 values in-place | Dutch National Flag |
| Majority element | Boyer-Moore Voting |
| Remove/move elements in-place | Write Pointer |
| Overlapping intervals | Sort + Merge |
| Product without self | Two-Pass Left-Right |
| Anagram / permutation | Frequency Array[26] |
| Longest palindrome substring | Expand from Center |
| Find pair with property | Hash Complement Lookup |
| Cycle in linked list | Floyd's Fast/Slow |
| Reverse linked list section | Iterative 3-pointer |
| Head might change | Dummy Node |
| Valid brackets | Stack matching |
| Next greater/smaller element | Monotonic Stack |
| Evaluate expression | Stack + operator precedence |
| Sliding window max/min | Monotonic Deque |
| Shortest path unweighted | BFS Queue |
| Top K elements | Min-Heap size K |
| Running median | Two Heaps |
| Merge K sorted | Heap of heads |
| Tree optimization | Tree DP (combine at node) |
| BST queries | Inorder = sorted |
| Prefix lookups | Trie |
| Max XOR pair | Binary Trie |
| Count islands | DFS/BFS Flood Fill |
| Grid paths / costs | DP on matrix |
| Search sorted matrix | Staircase from corner |
| Rotate matrix | Transpose + Reverse |
