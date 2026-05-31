# Queue Patterns

## Decision Flowchart

```
Need to process elements in order?
├─ Shortest path in unweighted graph? ──────────── BFS Level-Order
│   ├─ Multiple starting points? ───────────────── Multi-Source BFS
│   ├─ Search space too large? ─────────────────── Bidirectional BFS
│   ├─ Edge weights 0 or 1 only? ───────────────── 0-1 BFS (Deque)
│   └─ State is complex (not just position)? ───── BFS with State Encoding
├─ Need FIFO with fixed capacity? ──────────────── Circular Queue
├─ Simulate queue with stacks? ─────────────────── Two Stacks
└─ Simulate stack with queues? ─────────────────── Two Queues
```

---

## 1. BFS Level-Order

### Signal
- "Level by level" traversal, shortest path in unweighted graph, minimum steps/moves
- Tree level-order, zigzag, right side view

### Template (Java)

```java
Queue<Node> queue = new LinkedList<>();
queue.offer(start);
int level = 0;

while (!queue.isEmpty()) {
    int size = queue.size(); // SNAPSHOT current level size
    for (int i = 0; i < size; i++) {
        Node curr = queue.poll();
        // process curr at this level
        for (Node next : curr.neighbors()) {
            queue.offer(next);
        }
    }
    level++;
}
```

### Visualization

```
Queue state at each iteration:

Level 0: [1]          → process 1, enqueue 2,3
Level 1: [2, 3]      → process 2,3, enqueue 4,5,6
Level 2: [4, 5, 6]   → process 4,5,6

Tree:       1
          /   \
         2     3
        / \     \
       4   5     6
```

### Key Insight
`int size = queue.size()` before the inner loop freezes the boundary between levels. Without it, you mix levels.

### Variants
| Problem | Twist |
|---------|-------|
| Binary Tree Right Side View | Last element per level |
| Zigzag Level Order | Alternate insertion direction |
| Minimum Depth | Return level on first leaf hit |
| Shortest Path in Grid | BFS on 2D grid with visited[][] |

### Complexity
- Time: O(V + E) — each node/edge visited once
- Space: O(W) — max width of the level (worst case O(N))

---

## 2. Multi-Source BFS

### Signal
- "Minimum distance FROM multiple sources simultaneously"
- Rotting Oranges, 01 Matrix, Walls and Gates, shortest distance to any source

### Template (Java)

```java
Queue<int[]> queue = new LinkedList<>();
int[][] dist = new int[m][n];
// Initialize: enqueue ALL sources at once
for (int i = 0; i < m; i++)
    for (int j = 0; j < n; j++)
        if (isSource(grid[i][j])) {
            queue.offer(new int[]{i, j});
            dist[i][j] = 0;
        } else {
            dist[i][j] = Integer.MAX_VALUE;
        }

int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
while (!queue.isEmpty()) {
    int[] cell = queue.poll();
    for (int[] d : dirs) {
        int nr = cell[0] + d[0], nc = cell[1] + d[1];
        if (nr >= 0 && nr < m && nc >= 0 && nc < n
            && dist[nr][nc] > dist[cell[0]][cell[1]] + 1) {
            dist[nr][nc] = dist[cell[0]][cell[1]] + 1;
            queue.offer(new int[]{nr, nc});
        }
    }
}
```

### Visualization

```
Rotting Oranges (2=rotten, 1=fresh, 0=empty):

Initial:        t=0 sources:     t=1:            t=2:
[2, 1, 1]      [2, ., .]       [2, 2, .]       [2, 2, 2]
[1, 1, 0]      [., ., 0]       [2, ., 0]       [2, 2, 0]
[0, 1, 1]      [0, ., .]       [0, ., .]       [0, 2, .]

                                                 t=3: all rotten → answer=4
```

### Key Insight
By enqueuing all sources at t=0, BFS propagates a "wavefront" outward. Each cell gets the distance to its NEAREST source automatically — no need for N separate BFS runs.

### Variants
| Problem | Detail |
|---------|--------|
| 542. 01 Matrix | Sources = all 0-cells, find dist to nearest 0 |
| 286. Walls and Gates | Sources = gates (0), flood fill rooms (INF) |
| 994. Rotting Oranges | Sources = rotten, count levels until done |
| 1162. As Far from Land | Sources = land, find max dist water cell |

### Complexity
- Time: O(M * N)
- Space: O(M * N)

---

## 3. Bidirectional BFS

### Signal
- Shortest transformation/path between known start AND end
- Branching factor is large → search space explodes
- Word Ladder, gene mutation with known target

### Template (Java)

```java
Set<String> beginSet = new HashSet<>(), endSet = new HashSet<>();
Set<String> visited = new HashSet<>();
beginSet.add(beginWord);
endSet.add(endWord);
int level = 1;

while (!beginSet.isEmpty() && !endSet.isEmpty()) {
    // Always expand the SMALLER frontier
    if (beginSet.size() > endSet.size()) {
        Set<String> temp = beginSet;
        beginSet = endSet;
        endSet = temp;
    }
    
    Set<String> nextSet = new HashSet<>();
    for (String word : beginSet) {
        char[] arr = word.toCharArray();
        for (int i = 0; i < arr.length; i++) {
            char orig = arr[i];
            for (char c = 'a'; c <= 'z'; c++) {
                arr[i] = c;
                String next = new String(arr);
                
                if (endSet.contains(next)) return level + 1; // MEET!
                
                if (!visited.contains(next) && wordList.contains(next)) {
                    nextSet.add(next);
                    visited.add(next);
                }
            }
            arr[i] = orig;
        }
    }
    beginSet = nextSet;
    level++;
}
return 0; // no path
```

### Visualization

```
Regular BFS:  explores O(b^d) nodes        b=branching, d=depth
              ●━━━━━━━━━━━━━━━━━━━━●
              start                 end
              |←————— b^d ————————→|

Bidirectional: explores O(2 * b^(d/2)) nodes
              ●━━━━━━━━●●━━━━━━━━━●
              start   meet        end
              |←b^(d/2)→|←b^(d/2)→|

For b=26, d=10: single=26^10 vs bidirectional=2*26^5 ≈ 24M vs 141T
```

### Key Insight
Swap to always expand the smaller set. This keeps both frontiers balanced, minimizing total explored nodes.

### Complexity
- Time: O(b^(d/2)) instead of O(b^d)
- Space: O(b^(d/2)) for both frontiers

---

## 4. Circular Queue (Ring Buffer)

### Signal
- Fixed-size FIFO, streaming data, bounded buffer
- OS scheduling, producer-consumer, recent N items

### Template (Java)

```java
class MyCircularQueue {
    int[] data;
    int head, tail, size, capacity;
    
    public MyCircularQueue(int k) {
        data = new int[k];
        capacity = k;
        head = 0;
        tail = -1;
        size = 0;
    }
    
    public boolean enQueue(int value) {
        if (isFull()) return false;
        tail = (tail + 1) % capacity;  // wrap around
        data[tail] = value;
        size++;
        return true;
    }
    
    public boolean deQueue() {
        if (isEmpty()) return false;
        head = (head + 1) % capacity;  // wrap around
        size--;
        return true;
    }
    
    public int Front() { return isEmpty() ? -1 : data[head]; }
    public int Rear()  { return isEmpty() ? -1 : data[tail]; }
    public boolean isEmpty() { return size == 0; }
    public boolean isFull()  { return size == capacity; }
}
```

### Visualization

```
Capacity = 5, operations: enQ(1), enQ(2), enQ(3), deQ(), enQ(4), enQ(5), enQ(6)

[1, 2, 3, _, _]  head=0, tail=2, size=3
[_, 2, 3, _, _]  head=1, tail=2, size=2   (deQ)
[_, 2, 3, 4, 5]  head=1, tail=4, size=4
[6, 2, 3, 4, 5]  head=1, tail=0, size=5   (wrap! tail=(4+1)%5=0)
 ↑tail    ↑head
```

### Key Formula
```
next_index = (current + 1) % capacity
prev_index = (current - 1 + capacity) % capacity
```

### Complexity
- All operations: O(1) time, O(k) space

---

## 5. Queue Using Two Stacks

### Signal
- Design constraint: implement queue with only stack primitives
- Follow-up: amortized O(1) for all operations

### Template (Java)

```java
class MyQueue {
    Deque<Integer> inStack = new ArrayDeque<>();   // push here
    Deque<Integer> outStack = new ArrayDeque<>();  // pop from here
    
    public void push(int x) {
        inStack.push(x);
    }
    
    public int pop() {
        shiftIfNeeded();
        return outStack.pop();
    }
    
    public int peek() {
        shiftIfNeeded();
        return outStack.peek();
    }
    
    private void shiftIfNeeded() {
        if (outStack.isEmpty()) {
            while (!inStack.isEmpty()) {
                outStack.push(inStack.pop()); // reverses order → FIFO
            }
        }
    }
    
    public boolean empty() {
        return inStack.isEmpty() && outStack.isEmpty();
    }
}
```

### Visualization

```
push(1), push(2), push(3):
  inStack:  [3, 2, 1] (top→bottom)
  outStack: []

pop() → triggers shift:
  inStack:  []
  outStack: [1, 2, 3] (top→bottom)  ← reversed = FIFO order!
  returns 1

push(4), pop():
  inStack:  [4]
  outStack: [2, 3]  ← still has elements, no shift needed
  returns 2
```

### Key Insight
Each element is moved at most twice (once into inStack, once into outStack). Amortized O(1) per operation even though worst-case single pop is O(N).

### Complexity
- Push: O(1)
- Pop/Peek: Amortized O(1), worst case O(N)
- Space: O(N)

---

## 6. Stack Using Two Queues

### Signal
- Design constraint: implement stack with only queue primitives

### Template (Java) — Push-expensive variant

```java
class MyStack {
    Queue<Integer> q1 = new LinkedList<>();
    Queue<Integer> q2 = new LinkedList<>();
    
    public void push(int x) {
        q2.offer(x);
        while (!q1.isEmpty()) {
            q2.offer(q1.poll()); // move all old elements behind new one
        }
        // swap q1 and q2
        Queue<Integer> temp = q1;
        q1 = q2;
        q2 = temp;
    }
    
    public int pop()  { return q1.poll(); }
    public int top()  { return q1.peek(); }
    public boolean empty() { return q1.isEmpty(); }
}
```

### Single-Queue Optimization

```java
public void push(int x) {
    q1.offer(x);
    int sz = q1.size();
    // rotate everything before x to come after x
    for (int i = 0; i < sz - 1; i++) {
        q1.offer(q1.poll());
    }
}
```

### Visualization

```
push(1): q1=[1]
push(2): q2=[2] → move 1 behind → q2=[2,1] → swap → q1=[2,1]
push(3): q2=[3] → move 2,1 behind → q2=[3,2,1] → swap → q1=[3,2,1]

pop() → returns 3 (LIFO!)
q1=[2,1]
```

### Complexity
- Push: O(N) — must reorder
- Pop/Top: O(1)
- Space: O(N)

---

## 7. Priority Queue BFS / 0-1 BFS (Deque)

### Signal
- Graph with edge weights of ONLY 0 and 1
- "Minimum cost path" where transitions cost 0 or 1
- Swim in Rising Water, Minimum Obstacle Removal

### Template (Java) — 0-1 BFS with Deque

```java
Deque<int[]> deque = new ArrayDeque<>();
int[][] dist = new int[m][n];
for (int[] row : dist) Arrays.fill(row, Integer.MAX_VALUE);

deque.offerFirst(new int[]{0, 0});
dist[0][0] = 0;

int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
while (!deque.isEmpty()) {
    int[] curr = deque.pollFirst();
    int r = curr[0], c = curr[1];
    
    for (int[] d : dirs) {
        int nr = r + d[0], nc = c + d[1];
        if (nr < 0 || nr >= m || nc < 0 || nc >= n) continue;
        
        int weight = grid[nr][nc]; // 0 or 1
        int newDist = dist[r][c] + weight;
        
        if (newDist < dist[nr][nc]) {
            dist[nr][nc] = newDist;
            if (weight == 0)
                deque.offerFirst(new int[]{nr, nc});  // 0-cost → front
            else
                deque.offerLast(new int[]{nr, nc});   // 1-cost → back
        }
    }
}
return dist[m-1][n-1];
```

### Visualization

```
Grid (0=free, 1=obstacle):
[0, 1, 0]
[0, 0, 1]
[1, 0, 0]

Deque processing (front ← → back):
Step 0: [(0,0)]           dist[0][0]=0
Step 1: [(1,0), (0,1)]   0-cost→front, 1-cost→back
        Process (1,0): add (1,1)→front, (2,0)→back
        ...

Result: minimum obstacles to remove = dist[2][2]
```

### When to use what
| Condition | Algorithm |
|-----------|-----------|
| All edges weight 1 | Plain BFS |
| Edges weight 0 or 1 | 0-1 BFS (Deque) |
| Non-negative weights | Dijkstra (PriorityQueue) |
| Negative weights | Bellman-Ford |

### Complexity
- Time: O(V + E) — same as BFS since deque ops are O(1)
- Space: O(V)

---

## 8. BFS with State Encoding

### Signal
- State is NOT just a position — includes locks, keys, steps, configuration
- "Minimum moves to reach target configuration"
- Open the Lock, Sliding Puzzle, Shortest Path with Keys

### Template (Java)

```java
// State = encoded string (e.g., lock combo, puzzle config)
String start = "0000", target = "0202";
Set<String> visited = new HashSet<>(deadends);
if (visited.contains(start)) return -1;

Queue<String> queue = new LinkedList<>();
queue.offer(start);
visited.add(start);
int moves = 0;

while (!queue.isEmpty()) {
    int size = queue.size();
    for (int i = 0; i < size; i++) {
        String curr = queue.poll();
        if (curr.equals(target)) return moves;
        
        // Generate all neighbor states
        for (String next : getNeighbors(curr)) {
            if (!visited.contains(next)) {
                visited.add(next);
                queue.offer(next);
            }
        }
    }
    moves++;
}
return -1;

// For Open the Lock:
List<String> getNeighbors(String state) {
    List<String> neighbors = new ArrayList<>();
    char[] arr = state.toCharArray();
    for (int i = 0; i < 4; i++) {
        char orig = arr[i];
        arr[i] = (char)((orig - '0' + 1) % 10 + '0'); // turn up
        neighbors.add(new String(arr));
        arr[i] = (char)((orig - '0' + 9) % 10 + '0'); // turn down
        neighbors.add(new String(arr));
        arr[i] = orig;
    }
    return neighbors;
}
```

### Sliding Puzzle State

```java
// 773. Sliding Puzzle — state = board as string
// [[1,2,3],[4,0,5]] → "123405"
// Neighbors: swap 0 with adjacent positions

int[][] swaps = {{1,3},{0,2,4},{1,5},{0,4},{1,3,5},{2,4}};
// swaps[i] = positions that can swap with position i

List<String> getNeighbors(String state) {
    List<String> result = new ArrayList<>();
    int zeroIdx = state.indexOf('0');
    for (int swap : swaps[zeroIdx]) {
        char[] arr = state.toCharArray();
        arr[zeroIdx] = arr[swap];
        arr[swap] = '0';
        result.add(new String(arr));
    }
    return result;
}
```

### Visualization

```
Open the Lock: "0000" → "0202"  (deadends: ["0201","0101","0102","1212"])

Level 0: {"0000"}
Level 1: {"1000","9000","0100","0900","0010","0090","0001","0009"}
Level 2: {...expand each, skip deadends and visited...}
...until "0202" found

State graph is implicit — nodes are states, edges are single-move transitions.
Each state visited at most once → BFS guarantees shortest path.
```

### Composite State Pattern (BFS with extra dimensions)

```java
// Shortest path collecting keys: state = (row, col, keysBitmask)
// 864. Shortest Path to Get All Keys
String encode(int r, int c, int keys) {
    return r + "," + c + "," + keys;
}

// BFS over (position + collected keys) space
// Target: keys == (1 << totalKeys) - 1
```

### Complexity
- Time: O(S * B) — S = total states, B = branching per state
  - Open the Lock: O(10^4 * 8)
  - Sliding Puzzle: O(6! * 6) ≈ 4320
- Space: O(S) for visited set

---

## Summary Cheat Sheet

| Pattern | When | Key Trick |
|---------|------|-----------|
| Level-Order BFS | Tree/graph levels | `size = queue.size()` snapshot |
| Multi-Source BFS | Distance from ANY source | Enqueue all sources at t=0 |
| Bidirectional BFS | Known start + end, huge branching | Expand smaller frontier |
| Circular Queue | Fixed buffer, ring structure | `(i+1) % capacity` |
| Queue via 2 Stacks | Design / interview | Lazy transfer on empty outStack |
| Stack via 2 Queues | Design / interview | Rotate N-1 elements on push |
| 0-1 BFS | Binary edge weights | 0-cost→front, 1-cost→back |
| BFS + State | Complex configuration space | Encode state as string/bitmask |
