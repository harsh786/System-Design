# Heap & Priority Queue + Trie - Pattern Guide

---

# HEAP / PRIORITY QUEUE

## Pattern Recognition Signals

| Signal | Pattern |
|--------|---------|
| Kth largest/smallest | Min-heap of size K |
| Top K frequent | Count + Min-heap of size K (or bucket sort) |
| Merge K sorted lists/streams | Heap of list heads |
| Running median | Two heaps (max left, min right) |
| Scheduling with rooms/cooldown | Sort + Min-heap of end times |
| Rearrange no adjacent same | Max-heap + prev holder |
| Streaming data | Heap as priority buffer |

---

## Pattern 1: Top-K / Kth Largest

### Min-Heap of Size K
```java
PriorityQueue<Integer> minHeap = new PriorityQueue<>();
for (int num : nums) {
    minHeap.offer(num);
    if (minHeap.size() > k) minHeap.poll();  // evict smallest
}
return minHeap.peek();  // Kth largest = smallest in top-K set
```

### Why Min-Heap for Kth LARGEST?
```
Heap maintains K largest elements seen so far.
Root (min of these K) = the Kth largest overall.

nums = [3,2,1,5,6,4], k=2
Process: 3→[3], 2→[2,3], 1→[2,3](evict 1), 5→[3,5](evict 2), 
         6→[5,6](evict 3), 4→[5,6](evict 4)
peek() = 5 = 2nd largest ✓
```

### Comparison of Approaches
| Method | Time | Space | Online? |
|--------|------|-------|---------|
| Sort | O(n log n) | O(1) | No |
| Min-heap size K | O(n log k) | O(k) | Yes |
| QuickSelect | O(n) avg | O(1) | No |
| Bucket Sort (freq) | O(n) | O(n) | No |

---

## Pattern 2: Merge K Sorted Lists

```java
PriorityQueue<ListNode> pq = new PriorityQueue<>((a,b) -> a.val - b.val);
for (ListNode head : lists)
    if (head != null) pq.offer(head);

ListNode dummy = new ListNode(0), tail = dummy;
while (!pq.isEmpty()) {
    ListNode min = pq.poll();
    tail.next = min;
    tail = tail.next;
    if (min.next != null) pq.offer(min.next);
}
return dummy.next;
```

### K-Way Merge Generalization
```
Works for: K sorted lists, K sorted arrays, external sort, K sorted iterators
Key: always push the NEXT element from the same source as what was popped
Complexity: O(N log K) total
```

---

## Pattern 3: Two Heaps (Running Median)

```java
PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Collections.reverseOrder()); // left half
PriorityQueue<Integer> minHeap = new PriorityQueue<>();                           // right half

void addNum(int num) {
    maxHeap.offer(num);
    minHeap.offer(maxHeap.poll());         // balance: ensure all left ≤ all right
    if (minHeap.size() > maxHeap.size())
        maxHeap.offer(minHeap.poll());      // keep size: left >= right
}

double findMedian() {
    if (maxHeap.size() > minHeap.size()) return maxHeap.peek();
    return (maxHeap.peek() + minHeap.peek()) / 2.0;
}
```

### Invariants
```
┌──────────────┐  ┌──────────────┐
│   MAX HEAP   │  │   MIN HEAP   │
│ (left half)  │  │ (right half) │
│   smaller    │  │   larger     │
│  values      │  │  values      │
│  max at top  │  │  min at top  │
└──────────────┘  └──────────────┘
      ↕ top          top ↕
   ≤ median        ≥ median

Size: maxHeap.size() == minHeap.size() ± 1
Median: maxHeap.peek() (odd count) or avg of both peeks (even count)
```

---

## Pattern 4: Task Scheduling / Meeting Rooms with Heap

### Meeting Rooms II
```java
Arrays.sort(intervals, (a,b) -> a[0] - b[0]);  // sort by start
PriorityQueue<Integer> endTimes = new PriorityQueue<>();

for (int[] meeting : intervals) {
    if (!endTimes.isEmpty() && endTimes.peek() <= meeting[0])
        endTimes.poll();           // reuse freed room
    endTimes.offer(meeting[1]);    // allocate room
}
return endTimes.size();            // max concurrent
```

### Task Scheduler with Cooldown
```java
PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Collections.reverseOrder());
Queue<int[]> cooldown = new LinkedList<>();  // [freq, readyTime]
// Add all frequencies to maxHeap

int time = 0;
while (!maxHeap.isEmpty() || !cooldown.isEmpty()) {
    time++;
    if (!maxHeap.isEmpty()) {
        int freq = maxHeap.poll() - 1;
        if (freq > 0) cooldown.offer(new int[]{freq, time + n});
    }
    if (!cooldown.isEmpty() && cooldown.peek()[1] == time)
        maxHeap.offer(cooldown.poll()[0]);
}
return time;
```

---

## Pattern 5: Reorganize String / Distant Barcodes

```java
PriorityQueue<int[]> maxHeap = new PriorityQueue<>((a,b) -> b[1] - a[1]);
// Add [char, frequency] pairs

StringBuilder result = new StringBuilder();
int[] prev = null;

while (!maxHeap.isEmpty()) {
    int[] curr = maxHeap.poll();                 // most frequent available
    result.append((char) curr[0]);
    curr[1]--;
    if (prev != null && prev[1] > 0) maxHeap.offer(prev);  // push back prev
    prev = curr;                                  // hold current (can't use next turn)
}
return result.length() == s.length() ? result.toString() : "";
```

---

## Pattern 6: Lazy Deletion

```java
// When you need to "remove" arbitrary elements from heap
Map<Integer, Integer> deleteMap = new HashMap<>();  // element → count to delete

void lazyRemove(int val) {
    deleteMap.merge(val, 1, Integer::sum);
}

int lazyPeek(PriorityQueue<Integer> pq) {
    while (!pq.isEmpty() && deleteMap.containsKey(pq.peek())) {
        int top = pq.poll();
        deleteMap.merge(top, -1, Integer::sum);
        if (deleteMap.get(top) == 0) deleteMap.remove(top);
    }
    return pq.peek();
}
```

---

# TRIE

## Pattern Recognition Signals

| Signal | Pattern |
|--------|---------|
| Prefix-based lookup | Standard Trie |
| Autocomplete / suggestions | Trie + DFS from prefix |
| Wildcard '.' matching | Trie + DFS branching |
| Multiple words in grid | Trie + Backtracking |
| Maximum XOR of two numbers | Binary Trie |
| Longest common prefix | Trie traversal until branch |
| Word dictionary with delete | Trie with word count |

---

## Pattern 1: Standard Trie

```java
class TrieNode {
    TrieNode[] children = new TrieNode[26];
    boolean isEnd;
}

class Trie {
    TrieNode root = new TrieNode();
    
    void insert(String word) {
        TrieNode node = root;
        for (char c : word.toCharArray()) {
            int idx = c - 'a';
            if (node.children[idx] == null) node.children[idx] = new TrieNode();
            node = node.children[idx];
        }
        node.isEnd = true;
    }
    
    boolean search(String word) {
        TrieNode node = traverse(word);
        return node != null && node.isEnd;
    }
    
    boolean startsWith(String prefix) {
        return traverse(prefix) != null;
    }
    
    private TrieNode traverse(String s) {
        TrieNode node = root;
        for (char c : s.toCharArray()) {
            node = node.children[c - 'a'];
            if (node == null) return null;
        }
        return node;
    }
}
```

### Visualization
```
Insert: "apple", "app", "apt", "bat"

          root
         /    \
        a      b
        |      |
        p      a
       / \     |
      p   t    t(end)
      |  (end)
      l
      |
      e(end)
     (end) ← "app" ends here too
```

---

## Pattern 2: Wildcard Search ('.' = any)

```java
boolean search(String word, int idx, TrieNode node) {
    if (idx == word.length()) return node.isEnd;
    char c = word.charAt(idx);
    if (c == '.') {
        for (TrieNode child : node.children)
            if (child != null && search(word, idx + 1, child)) return true;
        return false;
    } else {
        TrieNode child = node.children[c - 'a'];
        return child != null && search(word, idx + 1, child);
    }
}
```

---

## Pattern 3: Word Search II (Trie-Guided Grid DFS)

```java
// Build trie from word list (store word at end node)
// DFS from each cell following trie edges

void dfs(char[][] board, int i, int j, TrieNode node, List<String> result) {
    if (node.word != null) {
        result.add(node.word);
        node.word = null;          // de-duplicate (don't find again)
    }
    if (i < 0 || i >= m || j < 0 || j >= n) return;
    char c = board[i][j];
    if (c == '#' || node.children[c-'a'] == null) return;
    
    board[i][j] = '#';            // mark visited
    TrieNode next = node.children[c - 'a'];
    dfs(board, i+1, j, next, result);
    dfs(board, i-1, j, next, result);
    dfs(board, i, j+1, next, result);
    dfs(board, i, j-1, next, result);
    board[i][j] = c;              // restore
    
    // PRUNE: if next has no children left, remove it
    if (isEmpty(next)) node.children[c-'a'] = null;
}
```

---

## Pattern 4: XOR Trie (Maximum XOR)

```java
class XORTrie {
    int[][] children = new int[32 * N][2];  // binary trie
    int idx = 0;
    
    void insert(int num) {
        int node = 0;
        for (int i = 31; i >= 0; i--) {
            int bit = (num >> i) & 1;
            if (children[node][bit] == 0) children[node][bit] = ++idx;
            node = children[node][bit];
        }
    }
    
    int maxXor(int num) {
        int node = 0, xor = 0;
        for (int i = 31; i >= 0; i--) {
            int bit = (num >> i) & 1;
            int want = 1 - bit;          // want opposite for max XOR
            if (children[node][want] != 0) {
                xor |= (1 << i);
                node = children[node][want];
            } else {
                node = children[node][bit];
            }
        }
        return xor;
    }
}
```

---

## Pattern 5: Autocomplete / Search Suggestions

```java
class AutocompleteTrie {
    TrieNode root = new TrieNode();
    
    List<String> suggest(String prefix, int limit) {
        TrieNode node = traverse(prefix);
        if (node == null) return List.of();
        
        List<String> result = new ArrayList<>();
        dfs(node, new StringBuilder(prefix), result, limit);
        return result;
    }
    
    void dfs(TrieNode node, StringBuilder sb, List<String> result, int limit) {
        if (result.size() >= limit) return;
        if (node.isEnd) result.add(sb.toString());
        for (int i = 0; i < 26; i++) {
            if (node.children[i] != null) {
                sb.append((char)('a' + i));
                dfs(node.children[i], sb, result, limit);
                sb.deleteCharAt(sb.length() - 1);
            }
        }
    }
}
```

---

## Pattern 6: Prefix Count / Score

```java
class TrieNode {
    TrieNode[] children = new TrieNode[26];
    int prefixCount = 0;  // words passing through this node
    int wordCount = 0;    // words ending here
}

void insert(String word) {
    TrieNode node = root;
    for (char c : word.toCharArray()) {
        if (node.children[c-'a'] == null) node.children[c-'a'] = new TrieNode();
        node = node.children[c-'a'];
        node.prefixCount++;
    }
    node.wordCount++;
}

int countWordsWithPrefix(String prefix) {
    TrieNode node = traverse(prefix);
    return node == null ? 0 : node.prefixCount;
}
```

---

## Trie vs HashMap vs TreeMap

| Operation | Trie | HashMap | TreeMap |
|-----------|------|---------|---------|
| Search | O(m) | O(m) avg | O(m log n) |
| Prefix search | O(m) | O(n*m) | O(m log n) |
| Autocomplete | O(m + results) | O(n*m) | O(m log n + results) |
| Space | O(alphabet * total chars) | O(n * avg_len) | O(n * avg_len) |
| Ordered iteration | Lexicographic ✓ | No | Yes ✓ |

**Use Trie when:** prefix operations, autocomplete, multiple pattern search, XOR queries
**Use HashMap when:** exact lookup only, no prefix needs
