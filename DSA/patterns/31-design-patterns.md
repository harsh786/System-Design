# 31 - OOP / Data Structure Design Patterns (LeetCode Interview)

## Interview Framework

```
1. CLARIFY   → Constraints, scale, thread-safety?, concurrency?
2. API       → Define public interface (method signatures)
3. DS CHOICE → Pick data structure combo (see Decision Flowchart)
4. CODE      → Implement with clean OOP
5. OPTIMIZE  → Amortized analysis, edge cases, follow-ups
```

---

## Decision Flowchart: Which DS Combo?

```
Need O(1) get + O(1) put with eviction?
├─ Evict least recently used  → HashMap + Doubly Linked List (LRU)
├─ Evict least frequently used → HashMap + Freq Buckets (DLL per freq) (LFU)
└─ Evict oldest               → Circular Buffer / Queue

Need O(1) insert + delete + getRandom?
└─ ArrayList + HashMap (swap-to-end trick)

Need O(1) min/max tracking?
└─ Auxiliary Stack (monotone tracking)

Need prefix-based search/autocomplete?
└─ Trie + DFS/BFS or Trie + Priority Queue

Need versioned/time-based lookups?
└─ Per-key list of (timestamp, value) + Binary Search

Need merge k sorted streams?
└─ Min-Heap of iterators (Design Twitter pattern)

Need ordered iteration + range queries?
└─ TreeMap (balanced BST)

Need serialize/deserialize tree?
├─ BFS → level-order with nulls
└─ DFS → preorder with sentinel
```

---

## Pattern 1: LRU Cache

### Signal
- O(1) get, O(1) put, evict least recently used on capacity overflow.

### Visualization
```
HashMap: key → Node
Doubly Linked List: HEAD ↔ [MRU] ↔ ... ↔ [LRU] ↔ TAIL

put(3,v): insert node after HEAD, if over capacity remove TAIL.prev
get(2):   move node to after HEAD, return value
```

### Template (Java)

```java
class LRUCache {
    private class Node {
        int key, val;
        Node prev, next;
        Node(int k, int v) { key = k; val = v; }
    }

    private int capacity;
    private Map<Integer, Node> map = new HashMap<>();
    private Node head = new Node(0, 0), tail = new Node(0, 0);

    public LRUCache(int capacity) {
        this.capacity = capacity;
        head.next = tail;
        tail.prev = head;
    }

    public int get(int key) {
        if (!map.containsKey(key)) return -1;
        Node node = map.get(key);
        remove(node);
        insertAfterHead(node);
        return node.val;
    }

    public void put(int key, int value) {
        if (map.containsKey(key)) remove(map.get(key));
        if (map.size() == capacity) {
            Node lru = tail.prev;
            remove(lru);
            map.remove(lru.key);
        }
        Node node = new Node(key, value);
        insertAfterHead(node);
        map.put(key, node);
    }

    private void remove(Node node) {
        node.prev.next = node.next;
        node.next.prev = node.prev;
    }

    private void insertAfterHead(Node node) {
        node.next = head.next;
        node.prev = head;
        head.next.prev = node;
        head.next = node;
    }
}
```

### Complexity
| Op  | Time | Space |
|-----|------|-------|
| get | O(1) | O(n)  |
| put | O(1) | O(n)  |

### Variants
- **LRU with TTL**: Add `expiry` field to Node, lazy-check on get.
- **Thread-safe LRU**: `ReentrantReadWriteLock` or `ConcurrentHashMap` + `synchronized` DLL ops.
- **LC 146**: LRU Cache (Medium)

---

## Pattern 2: LFU Cache

### Signal
- O(1) get, O(1) put, evict least frequently used (tie-break: least recent).

### Visualization
```
freqMap: freq → DoublyLinkedList of nodes at that frequency
keyMap:  key  → Node
minFreq: tracks current minimum frequency

put(k,v): insert at freq=1 bucket, update minFreq=1
get(k):   move node from freq bucket to freq+1 bucket
evict:    remove tail of freqMap[minFreq]
```

### Template (Java)

```java
class LFUCache {
    private int capacity, minFreq;
    private Map<Integer, Node> keyMap = new HashMap<>();
    private Map<Integer, LinkedHashSet<Integer>> freqMap = new HashMap<>();

    private class Node {
        int key, val, freq;
        Node(int k, int v) { key = k; val = v; freq = 1; }
    }

    public LFUCache(int capacity) {
        this.capacity = capacity;
    }

    public int get(int key) {
        if (!keyMap.containsKey(key)) return -1;
        Node node = keyMap.get(key);
        updateFreq(node);
        return node.val;
    }

    public void put(int key, int value) {
        if (capacity == 0) return;
        if (keyMap.containsKey(key)) {
            Node node = keyMap.get(key);
            node.val = value;
            updateFreq(node);
            return;
        }
        if (keyMap.size() == capacity) {
            LinkedHashSet<Integer> minSet = freqMap.get(minFreq);
            int evictKey = minSet.iterator().next();
            minSet.remove(evictKey);
            keyMap.remove(evictKey);
        }
        Node node = new Node(key, value);
        keyMap.put(key, node);
        minFreq = 1;
        freqMap.computeIfAbsent(1, k -> new LinkedHashSet<>()).add(key);
    }

    private void updateFreq(Node node) {
        int freq = node.freq;
        freqMap.get(freq).remove(node.key);
        if (freqMap.get(freq).isEmpty()) {
            freqMap.remove(freq);
            if (minFreq == freq) minFreq++;
        }
        node.freq++;
        freqMap.computeIfAbsent(node.freq, k -> new LinkedHashSet<>()).add(node.key);
    }
}
```

### Complexity
| Op  | Time | Space |
|-----|------|-------|
| get | O(1) | O(n)  |
| put | O(1) | O(n)  |

### Variants
- **LC 460**: LFU Cache (Hard)
- Use DLL per bucket instead of `LinkedHashSet` for pure O(1) with no amortization.

---

## Pattern 3: Min Stack / Max Stack

### Signal
- push, pop, top, getMin/getMax all in O(1).

### Visualization
```
Main Stack:  [3, 5, 2, 1, 4]
Min Stack:   [3, 3, 2, 1, 1]  ← tracks min at each level

push(x): minStack.push(min(x, minStack.peek()))
pop():   pop both stacks
getMin(): minStack.peek()
```

### Template (Java)

```java
class MinStack {
    private Deque<Integer> stack = new ArrayDeque<>();
    private Deque<Integer> minStack = new ArrayDeque<>();

    public void push(int val) {
        stack.push(val);
        minStack.push(minStack.isEmpty() ? val : Math.min(val, minStack.peek()));
    }

    public void pop() {
        stack.pop();
        minStack.pop();
    }

    public int top() { return stack.peek(); }
    public int getMin() { return minStack.peek(); }
}
```

### Complexity
| Op     | Time | Space |
|--------|------|-------|
| All    | O(1) | O(n)  |

### Variants
- **Max Stack (LC 716)**: Use TreeMap + DLL for O(log n) popMax.
- **Space-optimized**: Store `val - min` in stack; reconstruct on pop.
- **LC 155**: Min Stack (Medium)

---

## Pattern 4: Design HashMap / HashSet

### Signal
- Implement hash table from scratch with put/get/remove.

### Visualization
```
Chaining:
buckets[hash % size] → LinkedList of (key, val) pairs

Open Addressing (Linear Probing):
slots[hash % size], if occupied try (hash+1) % size, ...
```

### Template (Java) - Separate Chaining

```java
class MyHashMap {
    private static final int SIZE = 1009; // prime bucket count
    private List<int[]>[] buckets;

    public MyHashMap() {
        buckets = new LinkedList[SIZE];
    }

    private int hash(int key) { return key % SIZE; }

    public void put(int key, int value) {
        int idx = hash(key);
        if (buckets[idx] == null) buckets[idx] = new LinkedList<>();
        for (int[] pair : buckets[idx]) {
            if (pair[0] == key) { pair[1] = value; return; }
        }
        buckets[idx].add(new int[]{key, value});
    }

    public int get(int key) {
        int idx = hash(key);
        if (buckets[idx] == null) return -1;
        for (int[] pair : buckets[idx]) {
            if (pair[0] == key) return pair[1];
        }
        return -1;
    }

    public void remove(int key) {
        int idx = hash(key);
        if (buckets[idx] == null) return;
        buckets[idx].removeIf(pair -> pair[0] == key);
    }
}
```

### Complexity
| Op     | Avg  | Worst | Space |
|--------|------|-------|-------|
| All    | O(1) | O(n/k)| O(n) |

### Variants
- **Resizing**: Double buckets when load factor > 0.75, rehash all entries.
- **Open addressing**: Better cache locality, worse at high load factors.
- **LC 705/706**: Design HashSet / HashMap (Easy)

---

## Pattern 5: Design Twitter

### Signal
- postTweet, getNewsFeed (merge k sorted lists), follow/unfollow.

### Visualization
```
User 1 follows [2, 3]
User 1 tweets: [(t=10, id=5)]
User 2 tweets: [(t=8, id=3), (t=12, id=7)]
User 3 tweets: [(t=11, id=6)]

getNewsFeed(1): merge top 10 from all followed users' tweet lists
→ Min-heap of k iterators (one per user), extract top 10 by timestamp
```

### Template (Java)

```java
class Twitter {
    private int timestamp = 0;
    private Map<Integer, List<int[]>> tweets = new HashMap<>(); // userId → [(time, tweetId)]
    private Map<Integer, Set<Integer>> following = new HashMap<>();

    public void postTweet(int userId, int tweetId) {
        tweets.computeIfAbsent(userId, k -> new ArrayList<>()).add(new int[]{timestamp++, tweetId});
    }

    public List<Integer> getNewsFeed(int userId) {
        // Max-heap by timestamp
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> b[0] - a[0]);
        Set<Integer> users = new HashSet<>(following.getOrDefault(userId, Set.of()));
        users.add(userId);

        for (int uid : users) {
            List<int[]> userTweets = tweets.getOrDefault(uid, List.of());
            // Add last tweet of each user as starting point
            if (!userTweets.isEmpty()) {
                int idx = userTweets.size() - 1;
                int[] t = userTweets.get(idx);
                pq.offer(new int[]{t[0], t[1], uid, idx});
            }
        }

        List<Integer> feed = new ArrayList<>();
        while (!pq.isEmpty() && feed.size() < 10) {
            int[] top = pq.poll();
            feed.add(top[1]);
            int idx = top[3] - 1;
            if (idx >= 0) {
                int[] prev = tweets.get(top[2]).get(idx);
                pq.offer(new int[]{prev[0], prev[1], top[2], idx});
            }
        }
        return feed;
    }

    public void follow(int followerId, int followeeId) {
        following.computeIfAbsent(followerId, k -> new HashSet<>()).add(followeeId);
    }

    public void unfollow(int followerId, int followeeId) {
        following.getOrDefault(followerId, Set.of()).remove(followeeId);
    }
}
```

### Complexity
| Op          | Time         | Space |
|-------------|--------------|-------|
| postTweet   | O(1)         | O(T)  |
| getNewsFeed | O(K log K + 10 log K) | O(K) |
| follow/unfollow | O(1)    | O(U*U)|

Where K = number of followees, T = total tweets, U = users.

### Variants
- **LC 355**: Design Twitter (Medium)
- Pagination: Use cursor-based feed with offset tracking.

---

## Pattern 6: Iterator Design

### Signal
- Flatten nested structure, peek without advancing, interleave multiple iterators.

### 6a: Flatten Nested List Iterator

```java
class NestedIterator implements Iterator<Integer> {
    private Deque<Iterator<NestedInteger>> stack = new ArrayDeque<>();

    public NestedIterator(List<NestedInteger> nestedList) {
        stack.push(nestedList.iterator());
    }

    public Integer next() {
        hasNext(); // ensure top is integer
        return stack.peek().next().getInteger();
    }

    public boolean hasNext() {
        while (!stack.isEmpty()) {
            if (!stack.peek().hasNext()) { stack.pop(); continue; }
            NestedInteger ni = stack.peek().next(); // peek-like via lookahead
            // Actually, use a different approach: flatten into deque eagerly or use stack of iterators
            if (ni.isInteger()) {
                // Put it back? Simpler approach below:
            }
        }
        return false;
    }
}
```

**Cleaner approach - Stack of NestedInteger:**

```java
class NestedIterator implements Iterator<Integer> {
    private Deque<NestedInteger> stack = new ArrayDeque<>();

    public NestedIterator(List<NestedInteger> nestedList) {
        for (int i = nestedList.size() - 1; i >= 0; i--)
            stack.push(nestedList.get(i));
    }

    public Integer next() {
        hasNext();
        return stack.pop().getInteger();
    }

    public boolean hasNext() {
        while (!stack.isEmpty() && !stack.peek().isInteger()) {
            List<NestedInteger> list = stack.pop().getList();
            for (int i = list.size() - 1; i >= 0; i--)
                stack.push(list.get(i));
        }
        return !stack.isEmpty();
    }
}
```

### 6b: Peeking Iterator

```java
class PeekingIterator implements Iterator<Integer> {
    private Iterator<Integer> iter;
    private Integer peeked;
    private boolean hasPeeked;

    public PeekingIterator(Iterator<Integer> iterator) { iter = iterator; }

    public Integer peek() {
        if (!hasPeeked) { peeked = iter.next(); hasPeeked = true; }
        return peeked;
    }

    public Integer next() {
        if (hasPeeked) { hasPeeked = false; return peeked; }
        return iter.next();
    }

    public boolean hasNext() { return hasPeeked || iter.hasNext(); }
}
```

### 6c: Zigzag Iterator

```java
class ZigzagIterator {
    private Queue<Iterator<Integer>> queue = new LinkedList<>();

    public ZigzagIterator(List<Integer> v1, List<Integer> v2) {
        if (!v1.isEmpty()) queue.offer(v1.iterator());
        if (!v2.isEmpty()) queue.offer(v2.iterator());
    }

    public int next() {
        Iterator<Integer> it = queue.poll();
        int val = it.next();
        if (it.hasNext()) queue.offer(it);
        return val;
    }

    public boolean hasNext() { return !queue.isEmpty(); }
}
```

### Complexity
| Iterator     | next()  | hasNext() | Space |
|-------------|---------|-----------|-------|
| Flatten     | O(1) am| O(L/N) am| O(D)  |
| Peeking     | O(1)   | O(1)      | O(1)  |
| Zigzag      | O(1)   | O(1)      | O(K)  |

D = max nesting depth, K = number of lists.

### Variants
- **LC 341**: Flatten Nested List Iterator
- **LC 284**: Peeking Iterator
- **LC 281**: Zigzag Iterator
- **BSTIterator (LC 173)**: Controlled inorder with stack, O(h) space.

---

## Pattern 7: Trie-based Design

### Signal
- Prefix search, autocomplete, word dictionary with wildcards.

### Visualization
```
Insert: "app", "apple", "ape"

        root
         |
         a
         |
         p
        / \
       p   e*
       |
       l
       |
       e*

* = isEnd marker
```

### Template (Java)

```java
class Trie {
    private class TrieNode {
        TrieNode[] children = new TrieNode[26];
        boolean isEnd;
        List<String> suggestions = new ArrayList<>(); // for autocomplete
    }

    private TrieNode root = new TrieNode();

    public void insert(String word) {
        TrieNode node = root;
        for (char c : word.toCharArray()) {
            if (node.children[c - 'a'] == null)
                node.children[c - 'a'] = new TrieNode();
            node = node.children[c - 'a'];
            // For autocomplete: maintain top-3 suggestions per node
            if (node.suggestions.size() < 3)
                node.suggestions.add(word);
        }
        node.isEnd = true;
    }

    public boolean search(String word) {
        TrieNode node = find(word);
        return node != null && node.isEnd;
    }

    public boolean startsWith(String prefix) {
        return find(prefix) != null;
    }

    public List<String> autocomplete(String prefix) {
        TrieNode node = find(prefix);
        return node == null ? List.of() : node.suggestions;
    }

    private TrieNode find(String s) {
        TrieNode node = root;
        for (char c : s.toCharArray()) {
            node = node.children[c - 'a'];
            if (node == null) return null;
        }
        return node;
    }
}
```

### Search with Wildcards (LC 211)

```java
public boolean searchWithDot(TrieNode node, String word, int idx) {
    if (idx == word.length()) return node.isEnd;
    char c = word.charAt(idx);
    if (c == '.') {
        for (TrieNode child : node.children)
            if (child != null && searchWithDot(child, word, idx + 1)) return true;
        return false;
    }
    return node.children[c - 'a'] != null && searchWithDot(node.children[c - 'a'], word, idx + 1);
}
```

### Complexity
| Op         | Time   | Space  |
|------------|--------|--------|
| insert     | O(L)   | O(L)   |
| search     | O(L)   | O(1)   |
| startsWith | O(L)   | O(1)   |
| wildcard   | O(26^L)| O(L)   |

L = word length.

### Variants
- **LC 208**: Implement Trie
- **LC 211**: Add and Search Word
- **LC 1268**: Search Suggestions System (Trie + sort or per-node top-k)
- **LC 642**: Design Search Autocomplete System

---

## Pattern 8: Circular Queue / Deque

### Signal
- Fixed-size queue, O(1) enqueue/dequeue, wrap-around array.

### Visualization
```
capacity = 5, head = 2, tail = 4 (next insert position)
[_, _, A, B, _, ]
       h     t

After enqueue(C): tail = 0
[_, _, A, B, C]
       h        t=0 (wrapped)
```

### Template (Java)

```java
class MyCircularQueue {
    private int[] data;
    private int head, tail, size, capacity;

    public MyCircularQueue(int k) {
        data = new int[k];
        capacity = k;
    }

    public boolean enQueue(int value) {
        if (isFull()) return false;
        data[tail] = value;
        tail = (tail + 1) % capacity;
        size++;
        return true;
    }

    public boolean deQueue() {
        if (isEmpty()) return false;
        head = (head + 1) % capacity;
        size--;
        return true;
    }

    public int Front() { return isEmpty() ? -1 : data[head]; }
    public int Rear() { return isEmpty() ? -1 : data[(tail - 1 + capacity) % capacity]; }
    public boolean isEmpty() { return size == 0; }
    public boolean isFull() { return size == capacity; }
}
```

### Complexity
| Op       | Time | Space |
|----------|------|-------|
| All      | O(1) | O(k)  |

### Variants
- **LC 622**: Design Circular Queue
- **LC 641**: Design Circular Deque (add `insertFront`, `deleteLast`)
- Alternative: Use `(tail - head + capacity) % capacity` for size without counter.

---

## Pattern 9: Snapshot Array

### Signal
- set(index, val), snap() returns snap_id, get(index, snap_id).

### Visualization
```
index 0: [(snap=0, val=5), (snap=2, val=8)]
index 1: [(snap=1, val=3)]

get(0, 1) → binary search for largest snap_id <= 1 → val=5
get(0, 2) → snap_id=2 found → val=8
```

### Template (Java)

```java
class SnapshotArray {
    private List<int[]>[] history; // history[i] = list of [snap_id, val]
    private int snapId = 0;

    public SnapshotArray(int length) {
        history = new ArrayList[length];
        for (int i = 0; i < length; i++) {
            history[i] = new ArrayList<>();
            history[i].add(new int[]{0, 0});
        }
    }

    public void set(int index, int val) {
        List<int[]> h = history[index];
        if (h.get(h.size() - 1)[0] == snapId)
            h.get(h.size() - 1)[1] = val;
        else
            h.add(new int[]{snapId, val});
    }

    public int snap() { return snapId++; }

    public int get(int index, int snap_id) {
        List<int[]> h = history[index];
        // Binary search for largest snap <= snap_id
        int lo = 0, hi = h.size() - 1;
        while (lo < hi) {
            int mid = (lo + hi + 1) / 2;
            if (h.get(mid)[0] <= snap_id) lo = mid;
            else hi = mid - 1;
        }
        return h.get(lo)[1];
    }
}
```

### Complexity
| Op   | Time      | Space            |
|------|-----------|------------------|
| set  | O(1)      | O(S) total sets  |
| snap | O(1)      | O(1)             |
| get  | O(log S)  | O(1)             |

S = number of set operations.

### Variants
- **LC 1146**: Snapshot Array (Medium)
- Could use TreeMap<Integer, Integer> per index (cleaner but higher constant).

---

## Pattern 10: Time Based Key-Value Store

### Signal
- set(key, value, timestamp), get(key, timestamp) returns value with largest ts <= given ts.

### Visualization
```
key="foo": [(ts=1, "bar"), (ts=4, "baz")]

get("foo", 3) → binary search → ts=1 → "bar"
get("foo", 4) → ts=4 → "baz"
```

### Template (Java)

```java
class TimeMap {
    private Map<String, List<long[]>> map = new HashMap<>(); // values stored separately
    private Map<String, List<String>> vals = new HashMap<>();

    public void set(String key, String value, int timestamp) {
        map.computeIfAbsent(key, k -> new ArrayList<>()).add(new long[]{timestamp});
        vals.computeIfAbsent(key, k -> new ArrayList<>()).add(value);
    }

    public String get(String key, int timestamp) {
        if (!map.containsKey(key)) return "";
        List<long[]> times = map.get(key);
        // Binary search for largest ts <= timestamp
        int lo = 0, hi = times.size() - 1, ans = -1;
        while (lo <= hi) {
            int mid = (lo + hi) / 2;
            if (times.get(mid)[0] <= timestamp) { ans = mid; lo = mid + 1; }
            else hi = mid - 1;
        }
        return ans == -1 ? "" : vals.get(key).get(ans);
    }
}
```

**Cleaner with TreeMap:**

```java
class TimeMap {
    private Map<String, TreeMap<Integer, String>> map = new HashMap<>();

    public void set(String key, String value, int timestamp) {
        map.computeIfAbsent(key, k -> new TreeMap<>()).put(timestamp, value);
    }

    public String get(String key, int timestamp) {
        TreeMap<Integer, String> tree = map.get(key);
        if (tree == null) return "";
        Map.Entry<Integer, String> entry = tree.floorEntry(timestamp);
        return entry == null ? "" : entry.getValue();
    }
}
```

### Complexity
| Approach    | set      | get       | Space |
|-------------|----------|-----------|-------|
| BinarySearch| O(1)     | O(log n)  | O(n)  |
| TreeMap     | O(log n) | O(log n)  | O(n)  |

n = number of set calls per key.

### Variants
- **LC 981**: Time Based Key-Value Store (Medium)
- If timestamps always increasing, binary search is preferred (O(1) insert).

---

## Pattern 11: Design Hit Counter

### Signal
- hit(timestamp), getHits(timestamp) returns hits in past 300 seconds.

### Visualization
```
Circular buffer of size 300:
times[ts % 300] = ts
hits[ts % 300]  = count

If times[idx] == ts → increment hits[idx]
If times[idx] != ts → reset: times[idx] = ts, hits[idx] = 1

getHits: sum hits[i] where times[i] > timestamp - 300
```

### Template (Java)

```java
class HitCounter {
    private int[] times = new int[300];
    private int[] hits = new int[300];

    public void hit(int timestamp) {
        int idx = timestamp % 300;
        if (times[idx] != timestamp) {
            times[idx] = timestamp;
            hits[idx] = 1;
        } else {
            hits[idx]++;
        }
    }

    public int getHits(int timestamp) {
        int count = 0;
        for (int i = 0; i < 300; i++) {
            if (timestamp - times[i] < 300)
                count += hits[i];
        }
        return count;
    }
}
```

### Complexity
| Op      | Time  | Space |
|---------|-------|-------|
| hit     | O(1)  | O(W)  |
| getHits | O(W)  | O(1)  |

W = window size (300).

### Variants
- **LC 362**: Design Hit Counter (Medium)
- **Queue approach**: `Queue<Integer>`, dequeue expired timestamps. O(1) hit, O(expired) getHits.
- **Scalable**: Bucket per second, sliding window, distributed counters.

---

## Pattern 12: Insert Delete GetRandom O(1)

### Signal
- insert, remove, getRandom all O(1) average.

### Visualization
```
list: [3, 7, 1, 9]    map: {3→0, 7→1, 1→2, 9→3}

remove(7):
  - swap list[1] with list[last] → [3, 9, 1, 7]
  - update map: 9→1
  - remove last: list=[3, 9, 1], map removes 7
```

### Template (Java)

```java
class RandomizedSet {
    private List<Integer> list = new ArrayList<>();
    private Map<Integer, Integer> map = new HashMap<>(); // val → index
    private Random rand = new Random();

    public boolean insert(int val) {
        if (map.containsKey(val)) return false;
        map.put(val, list.size());
        list.add(val);
        return true;
    }

    public boolean remove(int val) {
        if (!map.containsKey(val)) return false;
        int idx = map.get(val);
        int last = list.get(list.size() - 1);
        list.set(idx, last);
        map.put(last, idx);
        list.remove(list.size() - 1);
        map.remove(val);
        return true;
    }

    public int getRandom() {
        return list.get(rand.nextInt(list.size()));
    }
}
```

### Complexity
| Op        | Time    | Space |
|-----------|---------|-------|
| insert    | O(1) am| O(n)  |
| remove    | O(1)   | O(n)  |
| getRandom | O(1)   | O(1)  |

### Variants
- **LC 380**: Insert Delete GetRandom O(1)
- **LC 381**: With duplicates (map: val → Set of indices, swap any one).
- **Weighted random**: Track weights, use prefix sum + binary search.

---

## Pattern 13: Design File System / Browser History

### 13a: File System (Trie-based)

```java
class FileSystem {
    private class TrieNode {
        Map<String, TrieNode> children = new HashMap<>();
        int value = -1;
    }

    private TrieNode root = new TrieNode();

    public boolean createPath(String path, int value) {
        String[] parts = path.split("/");
        TrieNode node = root;
        for (int i = 1; i < parts.length - 1; i++) {
            if (!node.children.containsKey(parts[i])) return false;
            node = node.children.get(parts[i]);
        }
        String last = parts[parts.length - 1];
        if (node.children.containsKey(last)) return false;
        TrieNode newNode = new TrieNode();
        newNode.value = value;
        node.children.put(last, newNode);
        return true;
    }

    public int get(String path) {
        String[] parts = path.split("/");
        TrieNode node = root;
        for (int i = 1; i < parts.length; i++) {
            if (!node.children.containsKey(parts[i])) return -1;
            node = node.children.get(parts[i]);
        }
        return node.value;
    }
}
```

### 13b: Browser History (Stack / Array)

```java
class BrowserHistory {
    private List<String> history = new ArrayList<>();
    private int curr = 0;

    public BrowserHistory(String homepage) { history.add(homepage); }

    public void visit(String url) {
        // Discard forward history
        while (history.size() > curr + 1) history.remove(history.size() - 1);
        history.add(url);
        curr++;
    }

    public String back(int steps) {
        curr = Math.max(0, curr - steps);
        return history.get(curr);
    }

    public String forward(int steps) {
        curr = Math.min(history.size() - 1, curr + steps);
        return history.get(curr);
    }
}
```

### Complexity
| File System | Time           | Space |
|-------------|----------------|-------|
| createPath  | O(path length) | O(P)  |
| get         | O(path length) | O(1)  |

| Browser     | Time | Space |
|-------------|------|-------|
| visit       | O(F) | O(n)  |
| back/forward| O(1) | O(1)  |

F = forward entries discarded.

### Variants
- **LC 1166**: Design File System
- **LC 1472**: Design Browser History
- **Two-stack browser**: back-stack + forward-stack approach.

---

## Pattern 14: Serialize / Deserialize

### Signal
- Convert tree to string and back. Must preserve structure.

### 14a: BFS Level-Order

```java
public class Codec {
    public String serialize(TreeNode root) {
        if (root == null) return "";
        StringBuilder sb = new StringBuilder();
        Queue<TreeNode> q = new LinkedList<>();
        q.offer(root);
        while (!q.isEmpty()) {
            TreeNode node = q.poll();
            if (node == null) { sb.append("#,"); continue; }
            sb.append(node.val).append(",");
            q.offer(node.left);
            q.offer(node.right);
        }
        return sb.toString();
    }

    public TreeNode deserialize(String data) {
        if (data.isEmpty()) return null;
        String[] vals = data.split(",");
        TreeNode root = new TreeNode(Integer.parseInt(vals[0]));
        Queue<TreeNode> q = new LinkedList<>();
        q.offer(root);
        int i = 1;
        while (!q.isEmpty()) {
            TreeNode node = q.poll();
            if (!vals[i].equals("#")) {
                node.left = new TreeNode(Integer.parseInt(vals[i]));
                q.offer(node.left);
            }
            i++;
            if (!vals[i].equals("#")) {
                node.right = new TreeNode(Integer.parseInt(vals[i]));
                q.offer(node.right);
            }
            i++;
        }
        return root;
    }
}
```

### 14b: DFS Preorder

```java
public class Codec {
    public String serialize(TreeNode root) {
        StringBuilder sb = new StringBuilder();
        serializeDFS(root, sb);
        return sb.toString();
    }

    private void serializeDFS(TreeNode node, StringBuilder sb) {
        if (node == null) { sb.append("#,"); return; }
        sb.append(node.val).append(",");
        serializeDFS(node.left, sb);
        serializeDFS(node.right, sb);
    }

    private int idx;

    public TreeNode deserialize(String data) {
        idx = 0;
        String[] vals = data.split(",");
        return deserializeDFS(vals);
    }

    private TreeNode deserializeDFS(String[] vals) {
        if (vals[idx].equals("#")) { idx++; return null; }
        TreeNode node = new TreeNode(Integer.parseInt(vals[idx++]));
        node.left = deserializeDFS(vals);
        node.right = deserializeDFS(vals);
        return node;
    }
}
```

### Complexity
| Approach | Serialize | Deserialize | Space  |
|----------|-----------|-------------|--------|
| BFS      | O(n)      | O(n)        | O(n)   |
| DFS      | O(n)      | O(n)        | O(h)*  |

*h = tree height for recursion stack; output string is O(n) regardless.

### Variants
- **LC 297**: Serialize and Deserialize Binary Tree (Hard)
- **LC 449**: Serialize BST (can omit nulls, use BST property for bounds)
- **N-ary tree**: Store child count per node.

---

## Amortized Complexity Summary

| Pattern              | Key Insight                              |
|---------------------|------------------------------------------|
| LRU/LFU             | HashMap gives O(1) lookup; DLL gives O(1) reorder |
| RandomizedSet       | ArrayList gives O(1) random; swap trick gives O(1) delete |
| Circular Buffer     | Modulo arithmetic avoids shifting        |
| Snapshot Array      | Only store diffs; binary search versions |
| Hit Counter         | Circular overwrite = implicit expiration |
| Trie Autocomplete   | Per-node top-k avoids full DFS at query time |
| Twitter Feed        | Merge-k-sorted via heap = optimal for top-N |

---

## Common Follow-ups in Interviews

| Question | Answer |
|----------|--------|
| "Make it thread-safe" | `ReadWriteLock`, `ConcurrentHashMap`, or `synchronized` blocks on mutation |
| "Scale to distributed" | Shard by key hash, use consistent hashing, gossip protocol for membership |
| "Handle memory pressure" | Eviction policy (LRU/LFU/TTL), off-heap storage, tiered caching |
| "Support persistence" | WAL (write-ahead log) + periodic snapshots |
| "Optimize for read-heavy" | Read replicas, cache-aside pattern, eventual consistency |
