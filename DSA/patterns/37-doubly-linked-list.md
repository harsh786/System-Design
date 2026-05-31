# Pattern 37: Doubly Linked List (DLL) Patterns

## Decision Flowchart

```
Need O(1) insertion/deletion at KNOWN position?
├── Yes ─── Do you need backward traversal or deletion without head reference?
│           ├── Yes ─── USE DOUBLY LINKED LIST
│           └── No ──── Singly Linked List suffices
└── No ──── Consider Array/Deque

Need O(1) access + O(1) eviction (cache)?
├── Yes ─── HashMap + DLL (LRU/LFU)
└── No

Need ordered iteration + O(1) move-to-front?
├── Yes ─── DLL with sentinel nodes
└── No ──── Other structure

Need O(log n) search in linked structure?
├── Yes ─── Skip List (multi-level DLL)
└── No
```

## DLL vs Singly Linked List Decision

| Criterion | Singly LL | Doubly LL |
|-----------|-----------|-----------|
| Memory per node | 1 pointer | 2 pointers |
| Delete node given pointer | O(n) need prev | O(1) |
| Insert before given node | O(n) | O(1) |
| Traverse backward | Impossible | O(1) per step |
| Cache-friendliness | Slightly better | Slightly worse |
| Implementation complexity | Simple | Moderate |

**Rule**: Use DLL when you hold a direct reference to a node and need to remove/move it in O(1).

---

## Sentinel Node Pattern (Dummy Head/Tail)

```
Signal: Edge cases with empty list, insert at head/tail, delete only node
```

```java
class DLLWithSentinels {
    ListNode head, tail; // dummy sentinels
    
    DLLWithSentinels() {
        head = new ListNode(0);
        tail = new ListNode(0);
        head.next = tail;
        tail.prev = head;
    }
    
    // NO null checks needed - sentinels absorb edge cases
    void addAfter(ListNode pred, ListNode node) {
        node.prev = pred;
        node.next = pred.next;
        pred.next.prev = node;
        pred.next = node;
    }
    
    void remove(ListNode node) {
        node.prev.next = node.next;
        node.next.prev = node.prev;
    }
}
```

**Why sentinels matter**: Without them, every insert/delete requires 4+ null checks for head/tail boundary conditions. Sentinels guarantee every real node always has valid `prev` and `next`.

---

## Pattern 1: DLL Node Structure and Basic Operations

### Signal
- Need bidirectional traversal
- Need O(1) delete given a node reference
- Need insert before/after a known position

### Template (Java)

```java
class ListNode {
    int val;
    ListNode prev, next;
    ListNode(int val) { this.val = val; }
}

class DoublyLinkedList {
    ListNode head, tail;
    int size;
    
    DoublyLinkedList() {
        head = new ListNode(-1); // sentinel
        tail = new ListNode(-1); // sentinel
        head.next = tail;
        tail.prev = head;
        size = 0;
    }
    
    // O(1) - Insert at front (after head sentinel)
    void insertFront(int val) {
        ListNode node = new ListNode(val);
        node.next = head.next;
        node.prev = head;
        head.next.prev = node;
        head.next = node;
        size++;
    }
    
    // O(1) - Insert at back (before tail sentinel)
    void insertBack(int val) {
        ListNode node = new ListNode(val);
        node.prev = tail.prev;
        node.next = tail;
        tail.prev.next = node;
        tail.prev = node;
        size++;
    }
    
    // O(1) - Insert after a given node
    void insertAfter(ListNode pred, int val) {
        ListNode node = new ListNode(val);
        node.prev = pred;
        node.next = pred.next;
        pred.next.prev = node;
        pred.next = node;
        size++;
    }
    
    // O(1) - Delete a specific node (given reference)
    void delete(ListNode node) {
        node.prev.next = node.next;
        node.next.prev = node.prev;
        node.prev = null; // help GC, prevent dangling
        node.next = null;
        size--;
    }
    
    // O(n) - Traverse forward
    void traverseForward() {
        ListNode cur = head.next;
        while (cur != tail) {
            // process cur.val
            cur = cur.next;
        }
    }
    
    // O(n) - Traverse backward
    void traverseBackward() {
        ListNode cur = tail.prev;
        while (cur != head) {
            // process cur.val
            cur = cur.prev;
        }
    }
}
```

### Visualization

```
Sentinel Pattern:

  head(S) <--> [A] <--> [B] <--> [C] <--> tail(S)
  
Insert X after B:
  1. X.prev = B
  2. X.next = B.next (C)
  3. C.prev = X
  4. B.next = X
  
  head(S) <--> [A] <--> [B] <--> [X] <--> [C] <--> tail(S)

Delete B:
  1. A.next = C      (B.prev.next = B.next)
  2. C.prev = A      (B.next.prev = B.prev)
  
  head(S) <--> [A] <--> [C] <--> tail(S)
```

### Complexity
| Operation | Time | Space |
|-----------|------|-------|
| Insert front/back | O(1) | O(1) |
| Insert after node | O(1) | O(1) |
| Delete given node | O(1) | O(1) |
| Search by value | O(n) | O(1) |
| Traverse | O(n) | O(1) |

---

## Pattern 2: LRU Cache (HashMap + DLL)

### Signal
- "Design a cache with capacity"
- O(1) get and put
- Evict least recently used on capacity overflow
- LC 146

### Template (Java)

```java
class LRUCache {
    class Node {
        int key, val;
        Node prev, next;
        Node(int k, int v) { key = k; val = v; }
    }
    
    int capacity;
    Map<Integer, Node> map;
    Node head, tail; // sentinels
    
    public LRUCache(int capacity) {
        this.capacity = capacity;
        map = new HashMap<>();
        head = new Node(0, 0);
        tail = new Node(0, 0);
        head.next = tail;
        tail.prev = head;
    }
    
    public int get(int key) {
        if (!map.containsKey(key)) return -1;
        Node node = map.get(key);
        moveToHead(node);   // mark as recently used
        return node.val;
    }
    
    public void put(int key, int value) {
        if (map.containsKey(key)) {
            Node node = map.get(key);
            node.val = value;
            moveToHead(node);
        } else {
            Node node = new Node(key, value);
            map.put(key, node);
            addToHead(node);
            if (map.size() > capacity) {
                Node lru = removeTail();  // evict LRU
                map.remove(lru.key);      // KEY stored in node for this!
            }
        }
    }
    
    private void addToHead(Node node) {
        node.prev = head;
        node.next = head.next;
        head.next.prev = node;
        head.next = node;
    }
    
    private void removeNode(Node node) {
        node.prev.next = node.next;
        node.next.prev = node.prev;
    }
    
    private void moveToHead(Node node) {
        removeNode(node);
        addToHead(node);
    }
    
    private Node removeTail() {
        Node lru = tail.prev;
        removeNode(lru);
        return lru;
    }
}
```

### Visualization

```
LRU Cache Internal Structure (capacity=3):
                                                        
  HashMap                  Doubly Linked List            
  ┌───────────┐                                         
  │ key=1 ──────────┐    head(S) <--> [1,A] <--> [3,C] <--> [2,B] <--> tail(S)
  │ key=2 ────────────────────────────────────────┘ MRU                    LRU
  │ key=3 ──────────────────────────┘                   
  └───────────┘                                         
                                                        
  get(2): move node(2,B) to head                        
                                                        
  head(S) <--> [2,B] <--> [1,A] <--> [3,C] <--> tail(S)
               MRU                              LRU     
                                                        
  put(4,D) with capacity full: evict tail.prev (3,C)    
                                                        
  head(S) <--> [4,D] <--> [2,B] <--> [1,A] <--> tail(S)
               MRU                              LRU     

  Key Insight: Node stores KEY so we can remove from HashMap during eviction
```

### Why DLL + HashMap?
- **HashMap**: O(1) lookup by key -> node reference
- **DLL**: O(1) move-to-front (recently used), O(1) remove-from-tail (eviction)
- Node stores `key` so eviction can also remove from HashMap

### Complexity
| Operation | Time | Space |
|-----------|------|-------|
| get | O(1) | O(capacity) |
| put | O(1) | O(capacity) |
| evict | O(1) | - |

---

## Pattern 3: LFU Cache (Frequency Buckets as DLLs)

### Signal
- Evict least frequently used; ties broken by LRU
- O(1) get and put
- LC 460

### Template (Java)

```java
class LFUCache {
    class Node {
        int key, val, freq;
        Node prev, next;
        Node(int k, int v) { key = k; val = v; freq = 1; }
    }
    
    // Each frequency has its own DLL (acts as LRU within that freq)
    class DLList {
        Node head, tail;
        int size;
        DLList() {
            head = new Node(0, 0);
            tail = new Node(0, 0);
            head.next = tail;
            tail.prev = head;
            size = 0;
        }
        void addToHead(Node node) {
            node.next = head.next;
            node.prev = head;
            head.next.prev = node;
            head.next = node;
            size++;
        }
        void remove(Node node) {
            node.prev.next = node.next;
            node.next.prev = node.prev;
            size--;
        }
        Node removeTail() {
            Node lru = tail.prev;
            remove(lru);
            return lru;
        }
        boolean isEmpty() { return size == 0; }
    }
    
    int capacity, minFreq;
    Map<Integer, Node> keyToNode;
    Map<Integer, DLList> freqToList;
    
    public LFUCache(int capacity) {
        this.capacity = capacity;
        minFreq = 0;
        keyToNode = new HashMap<>();
        freqToList = new HashMap<>();
    }
    
    public int get(int key) {
        if (!keyToNode.containsKey(key)) return -1;
        Node node = keyToNode.get(key);
        updateFreq(node);
        return node.val;
    }
    
    public void put(int key, int value) {
        if (capacity == 0) return;
        if (keyToNode.containsKey(key)) {
            Node node = keyToNode.get(key);
            node.val = value;
            updateFreq(node);
        } else {
            if (keyToNode.size() == capacity) {
                // Evict from min frequency list (LRU within that freq)
                DLList minList = freqToList.get(minFreq);
                Node evict = minList.removeTail();
                keyToNode.remove(evict.key);
            }
            Node node = new Node(key, value);
            keyToNode.put(key, node);
            freqToList.computeIfAbsent(1, k -> new DLList()).addToHead(node);
            minFreq = 1; // new node always has freq=1
        }
    }
    
    private void updateFreq(Node node) {
        int oldFreq = node.freq;
        DLList oldList = freqToList.get(oldFreq);
        oldList.remove(node);
        
        // Update minFreq if we emptied the min frequency bucket
        if (oldFreq == minFreq && oldList.isEmpty()) {
            minFreq++;
        }
        
        node.freq++;
        freqToList.computeIfAbsent(node.freq, k -> new DLList()).addToHead(node);
    }
}
```

### Visualization

```
LFU Cache Structure:

  keyToNode: {A->nodeA, B->nodeB, C->nodeC, D->nodeD}
  minFreq: 1

  freqToList:
  ┌─────────┬──────────────────────────────────────────┐
  │ freq=1  │  head(S) <--> [D] <--> [C] <--> tail(S) │  <- evict from here
  │ freq=2  │  head(S) <--> [B] <--> tail(S)          │
  │ freq=5  │  head(S) <--> [A] <--> tail(S)          │
  └─────────┴──────────────────────────────────────────┘
                              MRU              LRU
                              (within each frequency bucket)

  On eviction: remove tail of freq=minFreq list (node C if D was added later)
  On access:   remove from old freq list, add to head of (freq+1) list
```

### Complexity
| Operation | Time | Space |
|-----------|------|-------|
| get | O(1) | O(capacity) |
| put | O(1) | O(capacity) |

---

## Pattern 4: All O(1) Data Structure (Inc/Dec Key)

### Signal
- `inc(key)`, `dec(key)`, `getMaxKey()`, `getMinKey()` all in O(1)
- LC 432

### Template (Java)

```java
class AllOne {
    class Bucket {
        int count;
        Set<String> keys;
        Bucket prev, next;
        Bucket(int count) {
            this.count = count;
            keys = new LinkedHashSet<>();
        }
    }
    
    Bucket head, tail; // sentinels (head.count=0, tail.count=MAX)
    Map<String, Integer> keyCount;
    Map<Integer, Bucket> countBucket;
    
    public AllOne() {
        head = new Bucket(Integer.MIN_VALUE);
        tail = new Bucket(Integer.MAX_VALUE);
        head.next = tail;
        tail.prev = head;
        keyCount = new HashMap<>();
        countBucket = new HashMap<>();
    }
    
    public void inc(String key) {
        int oldCount = keyCount.getOrDefault(key, 0);
        int newCount = oldCount + 1;
        keyCount.put(key, newCount);
        
        // Add to new bucket
        Bucket newBucket;
        if (countBucket.containsKey(newCount)) {
            newBucket = countBucket.get(newCount);
        } else {
            newBucket = new Bucket(newCount);
            countBucket.put(newCount, newBucket);
            // Insert after the old bucket (or after head if new key)
            Bucket prev = oldCount == 0 ? head : countBucket.get(oldCount);
            insertAfter(prev, newBucket);
        }
        newBucket.keys.add(key);
        
        // Remove from old bucket
        if (oldCount > 0) {
            Bucket oldBucket = countBucket.get(oldCount);
            oldBucket.keys.remove(key);
            if (oldBucket.keys.isEmpty()) {
                removeBucket(oldBucket);
                countBucket.remove(oldCount);
            }
        }
    }
    
    public void dec(String key) {
        int oldCount = keyCount.get(key);
        int newCount = oldCount - 1;
        
        if (newCount == 0) {
            keyCount.remove(key);
        } else {
            keyCount.put(key, newCount);
            Bucket newBucket;
            if (countBucket.containsKey(newCount)) {
                newBucket = countBucket.get(newCount);
            } else {
                newBucket = new Bucket(newCount);
                countBucket.put(newCount, newBucket);
                // Insert BEFORE the old bucket
                Bucket oldBucket = countBucket.get(oldCount);
                insertAfter(oldBucket.prev, newBucket);
            }
            newBucket.keys.add(key);
        }
        
        // Remove from old bucket
        Bucket oldBucket = countBucket.get(oldCount);
        oldBucket.keys.remove(key);
        if (oldBucket.keys.isEmpty()) {
            removeBucket(oldBucket);
            countBucket.remove(oldCount);
        }
    }
    
    public String getMaxKey() {
        return tail.prev == head ? "" : tail.prev.keys.iterator().next();
    }
    
    public String getMinKey() {
        return head.next == tail ? "" : head.next.keys.iterator().next();
    }
    
    private void insertAfter(Bucket prev, Bucket node) {
        node.next = prev.next;
        node.prev = prev;
        prev.next.prev = node;
        prev.next = node;
    }
    
    private void removeBucket(Bucket node) {
        node.prev.next = node.next;
        node.next.prev = node.prev;
    }
}
```

### Visualization

```
DLL of Buckets (sorted by count):

head(S) <--> [count=1, {d,e}] <--> [count=3, {b}] <--> [count=7, {a,c}] <--> tail(S)
              ^min                                         ^max

Maps:
  keyCount:    {a:7, b:3, c:7, d:1, e:1}
  countBucket: {1:bucket1, 3:bucket3, 7:bucket7}

inc("d"): move "d" from bucket(1) to bucket(2)
  - bucket(2) doesn't exist -> create, insert after bucket(1)
  - if bucket(1) becomes empty -> remove it

getMinKey() -> head.next.keys.first()  = "d" or "e"
getMaxKey() -> tail.prev.keys.first()  = "a" or "c"
```

### Complexity
| Operation | Time | Space |
|-----------|------|-------|
| inc/dec | O(1) | O(n) |
| getMax/getMin | O(1) | - |

---

## Pattern 5: Flatten a Multilevel Doubly Linked List

### Signal
- DLL nodes have a `child` pointer to another DLL
- Flatten into single-level DLL (DFS order)
- LC 430

### Template (Java)

```java
// Iterative (Stack-based) - preferred for interview clarity
class Solution {
    public Node flatten(Node head) {
        if (head == null) return null;
        
        Node cur = head;
        Deque<Node> stack = new ArrayDeque<>();
        
        while (cur != null) {
            if (cur.child != null) {
                // Save next (if exists) to resume later
                if (cur.next != null) {
                    stack.push(cur.next);
                }
                // Connect child as next
                cur.next = cur.child;
                cur.child.prev = cur;
                cur.child = null;  // clear child pointer
            }
            
            if (cur.next == null && !stack.isEmpty()) {
                // Reached end of a child list, resume saved next
                Node next = stack.pop();
                cur.next = next;
                next.prev = cur;
            }
            
            cur = cur.next;
        }
        return head;
    }
}

// Recursive DFS approach
class SolutionRecursive {
    public Node flatten(Node head) {
        flattenDFS(head);
        return head;
    }
    
    // Returns the TAIL of the flattened list
    private Node flattenDFS(Node head) {
        Node cur = head, last = head;
        
        while (cur != null) {
            Node next = cur.next;
            
            if (cur.child != null) {
                Node childTail = flattenDFS(cur.child);
                
                // Connect cur -> child
                cur.next = cur.child;
                cur.child.prev = cur;
                
                // Connect childTail -> next
                if (next != null) {
                    childTail.next = next;
                    next.prev = childTail;
                }
                
                cur.child = null;
                last = childTail;
            } else {
                last = cur;
            }
            
            cur = next;
        }
        return last;
    }
}
```

### Visualization

```
Input:
  1 <--> 2 <--> 3 <--> 4 <--> 5
               |
               6 <--> 7 <--> 8
                      |
                      9 <--> 10

Flatten (DFS order):
  1 <--> 2 <--> 3 <--> 6 <--> 7 <--> 9 <--> 10 <--> 8 <--> 4 <--> 5
```

### Complexity
| Approach | Time | Space |
|----------|------|-------|
| Iterative (stack) | O(n) | O(depth) |
| Recursive | O(n) | O(depth) call stack |

---

## Pattern 6: Design Browser History

### Signal
- `visit(url)`: visit new page, clear forward history
- `back(steps)`: go back up to `steps`
- `forward(steps)`: go forward up to `steps`
- LC 1472

### Template (Java)

```java
class BrowserHistory {
    class Node {
        String url;
        Node prev, next;
        Node(String url) { this.url = url; }
    }
    
    Node current;
    
    public BrowserHistory(String homepage) {
        current = new Node(homepage);
    }
    
    // O(1) - visit new URL, discard forward history
    public void visit(String url) {
        Node node = new Node(url);
        current.next = node;
        node.prev = current;
        // node.next = null implicitly (forward history cleared)
        current = node;
    }
    
    // O(steps) - go back at most `steps`
    public String back(int steps) {
        while (steps > 0 && current.prev != null) {
            current = current.prev;
            steps--;
        }
        return current.url;
    }
    
    // O(steps) - go forward at most `steps`
    public String forward(int steps) {
        while (steps > 0 && current.next != null) {
            current = current.next;
            steps--;
        }
        return current.url;
    }
}
```

### Visualization

```
After visit(A), visit(B), visit(C):
  [A] <--> [B] <--> [C]
                      ^ current

back(1):
  [A] <--> [B] <--> [C]
            ^ current

visit(D):  (forward history [C] is discarded)
  [A] <--> [B] <--> [D]
                      ^ current
```

### Complexity
| Operation | Time | Space |
|-----------|------|-------|
| visit | O(1) | O(1) |
| back/forward | O(min(steps, history_len)) | O(1) |
| Total space | - | O(n) visits |

---

## Pattern 7: Design Text Editor (Cursor Operations)

### Signal
- `addText(text)`: insert text at cursor
- `deleteText(k)`: delete k chars left of cursor
- `cursorLeft(k)` / `cursorRight(k)`: move cursor, return 10 chars left of cursor
- LC 2296

### Template (Java)

```java
class TextEditor {
    class CharNode {
        char ch;
        CharNode prev, next;
        CharNode(char c) { ch = c; }
    }
    
    CharNode head, tail, cursor; // cursor points to node LEFT of cursor position
    
    public TextEditor() {
        head = new CharNode('\0');
        tail = new CharNode('\0');
        head.next = tail;
        tail.prev = head;
        cursor = head; // cursor starts at beginning (left of all text)
    }
    
    // O(|text|)
    public void addText(String text) {
        for (char c : text.toCharArray()) {
            CharNode node = new CharNode(c);
            // Insert after cursor
            node.next = cursor.next;
            node.prev = cursor;
            cursor.next.prev = node;
            cursor.next = node;
            cursor = node; // advance cursor
        }
    }
    
    // O(k)
    public int deleteText(int k) {
        int deleted = 0;
        while (k > 0 && cursor != head) {
            CharNode toDelete = cursor;
            cursor = cursor.prev;
            cursor.next = toDelete.next;
            toDelete.next.prev = cursor;
            k--;
            deleted++;
        }
        return deleted;
    }
    
    // O(k)
    public String cursorLeft(int k) {
        while (k > 0 && cursor != head) {
            cursor = cursor.prev;
            k--;
        }
        return getLeftText();
    }
    
    // O(k)
    public String cursorRight(int k) {
        while (k > 0 && cursor.next != tail) {
            cursor = cursor.next;
            k--;
        }
        return getLeftText();
    }
    
    private String getLeftText() {
        StringBuilder sb = new StringBuilder();
        CharNode node = cursor;
        int count = 10;
        while (count > 0 && node != head) {
            sb.append(node.ch);
            node = node.prev;
            count--;
        }
        return sb.reverse().toString();
    }
}
```

### Visualization

```
Text: "hello" with cursor after 'l' (first l):

  head(S) <--> [h] <--> [e] <--> [l] <--> [l] <--> [o] <--> tail(S)
                                   ^cursor

deleteText(2): removes 'l', 'e'
  head(S) <--> [h] <--> [l] <--> [o] <--> tail(S)
                ^cursor

addText("XY"):
  head(S) <--> [h] <--> [X] <--> [Y] <--> [l] <--> [o] <--> tail(S)
                                   ^cursor
```

**Note**: For interview, a two-stack approach (left stack + right stack) is simpler and equally valid. DLL shines when you need O(1) arbitrary node operations beyond just cursor movement.

### Complexity
| Operation | Time | Space |
|-----------|------|-------|
| addText | O(len) | O(len) |
| deleteText | O(k) | O(1) |
| cursorLeft/Right | O(k) | O(1) |

---

## Pattern 8: Max Stack (DLL + TreeMap)

### Signal
- `push(x)`, `pop()`, `top()` - standard stack ops
- `peekMax()`, `popMax()` - peek/remove the maximum element
- All operations O(log n)
- LC 716

### Template (Java)

```java
class MaxStack {
    class Node {
        int val;
        Node prev, next;
        Node(int v) { val = v; }
    }
    
    Node head, tail;
    TreeMap<Integer, List<Node>> map; // val -> list of nodes (handles duplicates)
    
    public MaxStack() {
        head = new Node(0);
        tail = new Node(0);
        head.next = tail;
        tail.prev = head;
        map = new TreeMap<>();
    }
    
    // O(log n)
    public void push(int x) {
        Node node = new Node(x);
        // Add to top of stack (before tail)
        node.prev = tail.prev;
        node.next = tail;
        tail.prev.next = node;
        tail.prev = node;
        
        map.computeIfAbsent(x, k -> new ArrayList<>()).add(node);
    }
    
    // O(log n)
    public int pop() {
        Node top = tail.prev;
        removeNode(top);
        List<Node> list = map.get(top.val);
        list.remove(list.size() - 1);
        if (list.isEmpty()) map.remove(top.val);
        return top.val;
    }
    
    // O(1)
    public int top() {
        return tail.prev.val;
    }
    
    // O(log n)
    public int peekMax() {
        return map.lastKey();
    }
    
    // O(log n)
    public int popMax() {
        int maxVal = map.lastKey();
        List<Node> list = map.get(maxVal);
        Node node = list.remove(list.size() - 1); // most recent max
        if (list.isEmpty()) map.remove(maxVal);
        removeNode(node);
        return maxVal;
    }
    
    private void removeNode(Node node) {
        node.prev.next = node.next;
        node.next.prev = node.prev;
    }
}
```

### Visualization

```
push(5), push(1), push(7), push(3), push(7):

DLL (bottom to top):
  head(S) <--> [5] <--> [1] <--> [7] <--> [3] <--> [7] <--> tail(S)
                                                      ^top

TreeMap:
  { 1: [node1], 3: [node3], 5: [node5], 7: [node7a, node7b] }

popMax(): finds 7 via lastKey(), removes node7b (most recent) from DLL
  head(S) <--> [5] <--> [1] <--> [7] <--> [3] <--> tail(S)

Key Insight: DLL gives O(1) removal of any node once located via TreeMap
```

### Why DLL here?
- `popMax()` needs to remove an arbitrary node from the middle of the stack
- Array-based stack would require O(n) shift
- DLL: O(1) removal once you have the node reference (TreeMap provides it)

### Complexity
| Operation | Time | Space |
|-----------|------|-------|
| push | O(log n) | O(n) |
| pop | O(log n) | - |
| top | O(1) | - |
| peekMax | O(log n) | - |
| popMax | O(log n) | - |

---

## Pattern 9: Deque Implementation with DLL

### Signal
- O(1) insert/remove from both ends
- Need more than what ArrayDeque provides (e.g., node references for mid-removal)

### Template (Java)

```java
class DLLDeque<T> {
    class Node {
        T val;
        Node prev, next;
        Node(T val) { this.val = val; }
    }
    
    Node head, tail;
    int size;
    
    DLLDeque() {
        head = new Node(null);
        tail = new Node(null);
        head.next = tail;
        tail.prev = head;
        size = 0;
    }
    
    void addFirst(T val) {
        Node node = new Node(val);
        node.next = head.next;
        node.prev = head;
        head.next.prev = node;
        head.next = node;
        size++;
    }
    
    void addLast(T val) {
        Node node = new Node(val);
        node.prev = tail.prev;
        node.next = tail;
        tail.prev.next = node;
        tail.prev = node;
        size++;
    }
    
    T removeFirst() {
        if (size == 0) throw new NoSuchElementException();
        Node first = head.next;
        head.next = first.next;
        first.next.prev = head;
        size--;
        return first.val;
    }
    
    T removeLast() {
        if (size == 0) throw new NoSuchElementException();
        Node last = tail.prev;
        tail.prev = last.prev;
        last.prev.next = tail;
        size--;
        return last.val;
    }
    
    T peekFirst() { return size == 0 ? null : head.next.val; }
    T peekLast()  { return size == 0 ? null : tail.prev.val; }
    boolean isEmpty() { return size == 0; }
}
```

### When DLL Deque over ArrayDeque?
- Need O(1) removal of arbitrary node given a reference (e.g., in sliding window problems combined with HashMap)
- Need stable node references (array resize invalidates indices)
- Building LRU/LFU cache primitives

### Complexity
| Operation | Time | Space |
|-----------|------|-------|
| addFirst/addLast | O(1) | O(1) |
| removeFirst/removeLast | O(1) | O(1) |
| peek | O(1) | O(1) |

---

## Pattern 10: Skip List (Multi-level DLL for O(log n) Search)

### Signal
- Need O(log n) search/insert/delete in a linked structure
- Alternative to balanced BST with simpler implementation
- Probabilistic balancing (no rotations)
- LC 1206

### Template (Java)

```java
class Skiplist {
    static final int MAX_LEVEL = 16;
    static final double P = 0.5;
    
    class Node {
        int val;
        Node[] next; // next pointers at each level
        // For full DLL: Node[] prev; (optional, enables backward traversal)
        
        Node(int val, int level) {
            this.val = val;
            next = new Node[level + 1];
        }
    }
    
    Node head;
    int level; // current max level in use
    Random rand;
    
    public Skiplist() {
        head = new Node(-1, MAX_LEVEL);
        level = 0;
        rand = new Random();
    }
    
    // O(log n) average
    public boolean search(int target) {
        Node cur = head;
        for (int i = level; i >= 0; i--) {
            while (cur.next[i] != null && cur.next[i].val < target) {
                cur = cur.next[i];
            }
        }
        cur = cur.next[0];
        return cur != null && cur.val == target;
    }
    
    // O(log n) average
    public void add(int num) {
        Node[] update = new Node[MAX_LEVEL + 1];
        Node cur = head;
        
        // Find insertion point at each level
        for (int i = level; i >= 0; i--) {
            while (cur.next[i] != null && cur.next[i].val < num) {
                cur = cur.next[i];
            }
            update[i] = cur; // predecessor at level i
        }
        
        int newLevel = randomLevel();
        if (newLevel > level) {
            for (int i = level + 1; i <= newLevel; i++) {
                update[i] = head;
            }
            level = newLevel;
        }
        
        Node newNode = new Node(num, newLevel);
        for (int i = 0; i <= newLevel; i++) {
            newNode.next[i] = update[i].next[i];
            update[i].next[i] = newNode;
        }
    }
    
    // O(log n) average
    public boolean erase(int num) {
        Node[] update = new Node[MAX_LEVEL + 1];
        Node cur = head;
        
        for (int i = level; i >= 0; i--) {
            while (cur.next[i] != null && cur.next[i].val < num) {
                cur = cur.next[i];
            }
            update[i] = cur;
        }
        
        cur = cur.next[0];
        if (cur == null || cur.val != num) return false;
        
        for (int i = 0; i <= level; i++) {
            if (update[i].next[i] != cur) break;
            update[i].next[i] = cur.next[i];
        }
        
        while (level > 0 && head.next[level] == null) {
            level--;
        }
        return true;
    }
    
    private int randomLevel() {
        int lvl = 0;
        while (rand.nextDouble() < P && lvl < MAX_LEVEL) {
            lvl++;
        }
        return lvl;
    }
}
```

### Visualization

```
Skip List with values [3, 6, 7, 9, 12, 19, 21, 25]:

Level 3: head ──────────────────────────── 19 ──────────── null
Level 2: head ─────── 6 ────────────────── 19 ── 21 ────── null
Level 1: head ── 3 ── 6 ─────── 9 ── 12 ── 19 ── 21 ── 25 null
Level 0: head ── 3 ── 6 ── 7 ── 9 ── 12 ── 19 ── 21 ── 25 null

Search(12):
  L3: head -> 19 (too big, drop down)
  L2: head -> 6 -> 19 (too big, drop down)  
  L1: 6 -> 9 -> 12 (found!)

Each level is a linked list. Adding prev pointers makes each level a DLL,
enabling backward iteration (useful for range queries in reverse).
```

### Key Insights
- Each node promoted to level `k` with probability `p^k` (typically p=0.5)
- Expected O(log n) levels, O(n) total space
- Simpler to implement than AVL/Red-Black trees
- Used in Redis sorted sets, LevelDB/RocksDB memtables

### Complexity
| Operation | Average | Worst | Space |
|-----------|---------|-------|-------|
| search | O(log n) | O(n) | O(n) |
| insert | O(log n) | O(n) | O(log n) per node |
| delete | O(log n) | O(n) | - |

---

## Common Bugs and Pitfalls

### Bug 1: Forgetting to update `prev` pointer

```java
// WRONG - only updates next direction
node.next = pred.next;
pred.next = node;

// CORRECT - update all 4 pointers
node.next = pred.next;
node.prev = pred;
pred.next.prev = node;  // <-- commonly forgotten!
pred.next = node;
```

### Bug 2: Dangling references after deletion

```java
// WRONG - node still points into the list
void remove(Node node) {
    node.prev.next = node.next;
    node.next.prev = node.prev;
    // node.prev and node.next still reference list nodes!
}

// CORRECT - null out removed node's pointers
void remove(Node node) {
    node.prev.next = node.next;
    node.next.prev = node.prev;
    node.prev = null;
    node.next = null;
}
```

### Bug 3: Wrong order of pointer updates

```java
// WRONG - overwrites pred.next before reading it
pred.next = node;          // pred.next is now node, lost original!
node.next = pred.next;     // node.next = node (self-loop!)

// CORRECT - read before write
node.next = pred.next;     // save reference first
pred.next = node;          // now safe to overwrite
```

### Bug 4: Not storing key in LRU node

```java
// WRONG - can't remove from HashMap during eviction
class Node { int val; }

// CORRECT - need key to do: map.remove(evicted.key)
class Node { int key, val; }
```

### Bug 5: Off-by-one with sentinels

```java
// WRONG - iterating over sentinels
Node cur = head;
while (cur != null) { ... }  // processes sentinel head

// CORRECT
Node cur = head.next;
while (cur != tail) { ... }  // skips both sentinels
```

---

## Variants and Related Problems

| Problem | Pattern | Key Insight |
|---------|---------|-------------|
| LC 146 LRU Cache | HashMap + DLL | Node stores key for eviction |
| LC 460 LFU Cache | freq map + DLL per freq | minFreq tracking |
| LC 432 All O(1) | DLL of buckets | Buckets hold sets of keys |
| LC 430 Flatten Multilevel DLL | DFS/Stack | Return tail for reconnection |
| LC 1472 Browser History | DLL + cursor | visit() clears forward |
| LC 2296 Text Editor | DLL or two stacks | Cursor = position between nodes |
| LC 716 Max Stack | DLL + TreeMap | TreeMap locates, DLL removes O(1) |
| LC 1206 Skip List | Multi-level LL | Random level assignment |
| LC 355 Design Twitter | DLL + merge | Recent tweets per user |
| LC 379 Phone Directory | DLL of available | O(1) get/release |

---

## Summary: When to Reach for DLL

1. **O(1) arbitrary removal**: You have a reference to a node and need to remove it without traversal
2. **LRU/LFU eviction**: Combine with HashMap for O(1) cache operations
3. **Bidirectional traversal**: Browser history, undo/redo, text editors
4. **Ordered bucket management**: All O(1) data structure, frequency lists
5. **Stable references**: Unlike arrays, node references don't invalidate on insert/delete

**Memory cost**: One extra pointer per node. Almost always worth it when the pattern calls for it.
