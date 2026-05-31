# Queue & Monotonic Queue - Pattern Guide

---

## Pattern Recognition Signals

| Signal | Pattern |
|--------|---------|
| Shortest path (unweighted) | BFS with queue |
| Level-by-level processing | BFS level-order |
| Propagation from multiple sources | Multi-source BFS |
| Max/min in sliding window | Monotonic Deque |
| Shortest subarray with sum ≥ K | Monotonic Deque |
| Fixed-size buffer / circular | Circular Queue |
| Implement queue with stacks | Two-stack trick |

---

## Pattern 1: BFS Level-Order

**When:** Process graph/tree level by level, shortest path in unweighted graph.

### Template
```java
Queue<Node> queue = new LinkedList<>();
queue.offer(start);
Set<Node> visited = new HashSet<>();
visited.add(start);
int level = 0;

while (!queue.isEmpty()) {
    int size = queue.size();          // CRITICAL: snapshot current level
    for (int i = 0; i < size; i++) {
        Node node = queue.poll();
        process(node);
        for (Node neighbor : node.neighbors()) {
            if (!visited.contains(neighbor)) {
                visited.add(neighbor);
                queue.offer(neighbor);
            }
        }
    }
    level++;
}
```

### Key Insight: `size = queue.size()`
```
Without level tracking:  just process one at a time (shortest path)
With level tracking:     process ALL nodes at current distance together

Level 0: [A]           → process A, add B,C
Level 1: [B, C]       → process B,C, add D,E,F
Level 2: [D, E, F]    → process D,E,F
```

---

## Pattern 2: Multi-Source BFS

**When:** Propagation from multiple starting points simultaneously (rotting oranges, 01 matrix, walls & gates).

### Template
```java
Queue<int[]> queue = new LinkedList<>();
// Add ALL sources at once
for (int i = 0; i < m; i++)
    for (int j = 0; j < n; j++)
        if (isSource(grid[i][j])) {
            queue.offer(new int[]{i, j});
            visited[i][j] = true;
        }

// Standard BFS from here - all sources expand simultaneously
int distance = 0;
while (!queue.isEmpty()) {
    int size = queue.size();
    for (int i = 0; i < size; i++) {
        int[] cell = queue.poll();
        for (int[] dir : dirs) {
            int ni = cell[0] + dir[0], nj = cell[1] + dir[1];
            if (valid(ni, nj) && !visited[ni][nj]) {
                visited[ni][nj] = true;
                result[ni][nj] = distance + 1;
                queue.offer(new int[]{ni, nj});
            }
        }
    }
    distance++;
}
```

### Visualization: Rotting Oranges
```
Time 0:      Time 1:      Time 2:      Time 3:
2 1 1        2 2 1        2 2 2        2 2 2
1 1 0   →    2 1 0   →    2 2 0   →    2 2 0
0 1 1        0 1 1        0 2 1        0 2 2

Sources (2s) all start in queue simultaneously
BFS expands outward uniformly → answer = max distance = 3

If any 1 unreachable → return -1
```

---

## Pattern 3: Monotonic Deque (Sliding Window Max/Min)

**When:** Find maximum or minimum in every window of size K.

### Template: Sliding Window Maximum
```java
Deque<Integer> deque = new ArrayDeque<>();  // stores INDICES
int[] result = new int[n - k + 1];

for (int i = 0; i < n; i++) {
    // 1. Remove out-of-window elements from FRONT
    while (!deque.isEmpty() && deque.peekFirst() <= i - k) {
        deque.pollFirst();
    }
    
    // 2. Remove smaller elements from BACK (they can never be max)
    while (!deque.isEmpty() && nums[deque.peekLast()] <= nums[i]) {
        deque.pollLast();
    }
    
    // 3. Add current element
    deque.offerLast(i);
    
    // 4. Record answer once window is full
    if (i >= k - 1) {
        result[i - k + 1] = nums[deque.peekFirst()];
    }
}
```

### Visualization
```
nums = [1, 3, -1, -3, 5, 3, 6, 7], k = 3

i=0: deque=[0]       (values: [1])
i=1: deque=[1]       (values: [3])       — 1 removed (3>1, 1 can never be max)
i=2: deque=[1,2]     (values: [3,-1])    — window [1,3,-1], max=3 ✓
i=3: deque=[1,3]     (values: [3,-3])    — window [3,-1,-3], max=3 ✓
i=4: deque=[4]       (values: [5])       — 5>all, clear, window [-1,-3,5], max=5 ✓
i=5: deque=[4,5]     (values: [5,3])     — window [-3,5,3], max=5 ✓
i=6: deque=[6]       (values: [6])       — window [5,3,6], max=6 ✓
i=7: deque=[7]       (values: [7])       — window [3,6,7], max=7 ✓

INVARIANT: deque is always DECREASING (front=max, back=recent smaller)

WHY: An element can only be the max if all elements before it (and still in window) are ≤ it.
     If nums[i] > nums[j] and i > j, then j can NEVER be the max again → remove it.
```

### For Sliding Window Minimum: flip comparison
```java
// Remove LARGER elements from back (they can never be min)
while (!deque.isEmpty() && nums[deque.peekLast()] >= nums[i]) {
    deque.pollLast();
}
// Deque maintains INCREASING order (front=min)
```

**Complexity:** O(n) time (each element enters/exits deque once), O(k) space

---

## Pattern 4: Shortest Subarray with Sum ≥ K (Monotonic Deque on Prefix Sum)

**When:** Minimum length subarray with sum ≥ K (may have negative numbers).

### Template
```java
long[] prefix = new long[n + 1];
for (int i = 0; i < n; i++) prefix[i+1] = prefix[i] + nums[i];

Deque<Integer> deque = new ArrayDeque<>();  // increasing prefix sums
int result = Integer.MAX_VALUE;

for (int i = 0; i <= n; i++) {
    // If prefix[i] - prefix[deque.front] >= k → valid subarray
    while (!deque.isEmpty() && prefix[i] - prefix[deque.peekFirst()] >= k) {
        result = Math.min(result, i - deque.pollFirst());
    }
    // Maintain increasing order (remove from back if current prefix ≤ back)
    while (!deque.isEmpty() && prefix[i] <= prefix[deque.peekLast()]) {
        deque.pollLast();
    }
    deque.offerLast(i);
}
```

### Why Monotonic Deque Works Here
```
prefix: [0, 2, -1, 3, 8, 1]   (from nums [2, -3, 4, 5, -7])

Why remove larger prefixes from back?
  If prefix[i] ≤ prefix[j] and i > j, then for ANY future index r:
  prefix[r] - prefix[i] ≥ prefix[r] - prefix[j], AND i is closer to r.
  So j is DOMINATED by i → remove j.

Why remove from front when valid?
  Once prefix[r] - prefix[front] ≥ k, the front gave its best answer.
  Any future r' > r would give a longer subarray → remove front.
```

---

## Pattern 5: Circular Queue / Deque

**When:** Fixed-size buffer, producer-consumer, ring buffer.

### Template
```java
class MyCircularQueue {
    int[] data;
    int front = 0, size = 0, capacity;
    
    MyCircularQueue(int k) { data = new int[k]; capacity = k; }
    
    boolean enQueue(int val) {
        if (isFull()) return false;
        data[(front + size) % capacity] = val;
        size++;
        return true;
    }
    
    boolean deQueue() {
        if (isEmpty()) return false;
        front = (front + 1) % capacity;
        size--;
        return true;
    }
    
    int Front() { return isEmpty() ? -1 : data[front]; }
    int Rear() { return isEmpty() ? -1 : data[(front + size - 1) % capacity]; }
    boolean isEmpty() { return size == 0; }
    boolean isFull() { return size == capacity; }
}
```

### Visualization
```
capacity = 5
[_, _, _, _, _]   front=0, size=0

enQueue(1,2,3):
[1, 2, 3, _, _]   front=0, size=3

deQueue():
[_, 2, 3, _, _]   front=1, size=2

enQueue(4,5,6):
[6, 2, 3, 4, 5]   front=1, size=5 (wraps around!)
 ^ rear              ^ front
```

---

## Pattern 6: Queue Using Two Stacks

**When:** Implement queue with FIFO using stacks (LIFO).

### Template
```java
class MyQueue {
    Deque<Integer> inStack = new ArrayDeque<>();
    Deque<Integer> outStack = new ArrayDeque<>();
    
    void push(int x) { inStack.push(x); }
    
    int pop() {
        if (outStack.isEmpty()) transfer();
        return outStack.pop();
    }
    
    int peek() {
        if (outStack.isEmpty()) transfer();
        return outStack.peek();
    }
    
    private void transfer() {
        while (!inStack.isEmpty()) outStack.push(inStack.pop());
    }
}
```

### Why Amortized O(1)
```
Each element: push to inStack (O(1)), transfer to outStack (O(1) amortized), pop (O(1))
Total: each element moves exactly twice → amortized O(1) per operation

inStack:  [3, 2, 1]  ← push here
outStack: []

On pop:
inStack:  []
outStack: [1, 2, 3]  ← pop from here (gives 1 = FIFO order ✓)
```

---

## Pattern 7: Bidirectional BFS

**When:** Shortest path between two known endpoints. Reduces search space exponentially.

### Template
```java
Set<String> beginSet = new HashSet<>(Arrays.asList(beginWord));
Set<String> endSet = new HashSet<>(Arrays.asList(endWord));
Set<String> visited = new HashSet<>();
int level = 1;

while (!beginSet.isEmpty() && !endSet.isEmpty()) {
    // Always expand the SMALLER set (optimization)
    if (beginSet.size() > endSet.size()) swap(beginSet, endSet);
    
    Set<String> nextSet = new HashSet<>();
    for (String word : beginSet) {
        for (String neighbor : getNeighbors(word)) {
            if (endSet.contains(neighbor)) return level + 1;  // MEET!
            if (!visited.contains(neighbor)) {
                visited.add(neighbor);
                nextSet.add(neighbor);
            }
        }
    }
    beginSet = nextSet;
    level++;
}
return 0;  // no path
```

### Why It's Faster
```
Regular BFS: explores b^d nodes (b=branching, d=depth)
Bidirectional: explores 2 * b^(d/2) nodes

Example: b=10, d=6
  Regular: 10^6 = 1,000,000
  Bidir:   2 * 10^3 = 2,000   (500x faster!)
```

---

## Summary Flowchart

```
Queue Problem?
│
├─ Shortest path (unweighted)? ──→ BFS with queue
│
├─ Level-by-level processing? ───→ BFS + size snapshot per level
│
├─ Multiple start points? ──────→ Multi-source BFS
│
├─ Max/min in sliding window? ──→ Monotonic Deque (decreasing/increasing)
│
├─ Shortest subarray sum≥K? ────→ Monotonic Deque on prefix sums
│
├─ Fixed-size ring buffer? ─────→ Circular Queue (modular arithmetic)
│
├─ Two known endpoints? ────────→ Bidirectional BFS
│
└─ Queue from stacks? ──────────→ Two-stack amortized O(1)
```
