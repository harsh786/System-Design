# 40 - Data Stream Processing Patterns

## Core Philosophy

Stream processing answers: **How do you maintain answers over unbounded, incrementally arriving data with bounded memory?**

```
Online Algorithm: Process each element once, answer queries at any point
Offline Algorithm: Requires all data upfront before computing answer

Stream constraints:
- Cannot store all elements (space O(n) unacceptable or impractical)
- Must answer queries in O(1) or O(log n) per element
- May sacrifice exactness for space (probabilistic structures)
```

---

## Decision Flowchart

```
                    What query on the stream?
                            |
        ┌───────────┬──────┼──────┬────────────┬──────────────┐
        v           v      v      v            v              v
    Median/     Kth      Count/   Unique/    Frequency     Approx
    Quantile  Largest    Average  Dedup      Ranking      Counting
        |         |        |        |           |             |
   ┌────┴────┐   |        |        |      ┌────┴────┐        |
   v         v   v        v        v      v         v        v
 Global   Window MinHeap Queue  LHMap+  Heap+Map  TreeMap  Count-Min
 Two-Heap TreeMap size-k  /Ring  Queue   BucketSort         HyperLogLog
                  Buffer
```

### When to Use What

| Structure | Use When | Trade-off |
|-----------|----------|-----------|
| **Two Heaps** | Global median, no removals | O(1) find, O(log n) add |
| **TreeMap/Multiset** | Sliding window median, need removals | O(log n) all ops, handles dupes |
| **Queue/Ring Buffer** | Fixed-size window, simple aggregates | O(1) amortized, bounded space |
| **Min-Heap size k** | Kth largest only | O(log k) add, O(1) query |
| **HashMap + Heap** | Top-K frequency | O(n) space, O(n log k) recompute |
| **Count-Min Sketch** | Approximate frequency, massive streams | Sub-linear space, over-counts |
| **HyperLogLog** | Approximate cardinality | O(1) space practically, ~2% error |

---

## Pattern 1: Find Median from Data Stream

### Signal
- Continuous insertions, query median at any time
- No deletions required
- "Median", "middle element", "balanced partition"

### Visualization

```
Stream: 5, 2, 8, 1, 9, 3

Step-by-step:
  maxHeap (lower half)    minHeap (upper half)    Median
  [5]                     []                      5
  [2]                     [5]                     3.5
  [5, 2]                  [8]                     5
  [2, 1]                  [5, 8]                  3.5
  [5, 2, 1]              [8, 9]                  5
  [3, 2, 1]              [5, 8, 9]               4.0

Invariant: |maxHeap| == |minHeap| or |maxHeap| == |minHeap| + 1
           maxHeap.peek() <= minHeap.peek()

  ┌─────────────┐         ┌─────────────┐
  │  Max-Heap   │  <==>   │  Min-Heap   │
  │ (lower half)│         │ (upper half)│
  │  top = max  │  <=     │  top = min  │
  └─────────────┘         └─────────────┘
        │                        │
        └───── median is here ───┘
              (top of one or avg of both)
```

### Template (Java)

```java
class MedianFinder {
    // maxHeap stores lower half (largest of lower at top)
    PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Collections.reverseOrder());
    // minHeap stores upper half (smallest of upper at top)
    PriorityQueue<Integer> minHeap = new PriorityQueue<>();

    public void addNum(int num) {
        maxHeap.offer(num);
        minHeap.offer(maxHeap.poll()); // ensure ordering invariant

        // balance sizes: maxHeap can have at most 1 extra
        if (minHeap.size() > maxHeap.size()) {
            maxHeap.offer(minHeap.poll());
        }
    }

    public double findMedian() {
        if (maxHeap.size() > minHeap.size()) {
            return maxHeap.peek();
        }
        return (maxHeap.peek() + minHeap.peek()) / 2.0;
    }
}
```

### Complexity
- **Add**: O(log n)
- **Find Median**: O(1)
- **Space**: O(n)

### Variants
- Follow-up: If all integers in [0,100], use bucket counting array
- Follow-up: If 99% in [0,100], bucket + two heaps for outliers

---

## Pattern 2: Sliding Window Median

### Signal
- Fixed window of size k sliding across array
- Need median within each window position
- Requires efficient insertion AND deletion

### Visualization

```
Array: [1, 3, -1, -3, 5, 3, 6, 7], k = 3

Window      Sorted Window    Median
[1,3,-1]    [-1,1,3]         1
[3,-1,-3]   [-3,-1,3]       -1
[-1,-3,5]   [-3,-1,5]       -1
[-3,5,3]    [-3,3,5]         3
[5,3,6]     [3,5,6]          5
[3,6,7]     [3,6,7]          6

Two TreeMaps approach:
  lower (acts as max-heap)    upper (acts as min-heap)
  Lazy deletion: element leaves window -> adjust balance counter
```

### Template (Java)

```java
class SlidingWindowMedian {
    TreeMap<Integer, Integer> lower = new TreeMap<>(); // lower half (descending access)
    TreeMap<Integer, Integer> upper = new TreeMap<>(); // upper half (ascending access)
    int lowerSize = 0, upperSize = 0;

    public double[] medianSlidingWindow(int[] nums, int k) {
        double[] result = new double[nums.length - k + 1];

        for (int i = 0; i < nums.length; i++) {
            addNum(nums[i]);

            if (i >= k) {
                removeNum(nums[i - k]);
            }

            rebalance();

            if (i >= k - 1) {
                result[i - k + 1] = getMedian(k);
            }
        }
        return result;
    }

    private void addNum(int num) {
        // Add to lower first, then balance
        if (lowerSize == 0 || num <= lower.lastKey()) {
            lower.merge(num, 1, Integer::sum);
            lowerSize++;
        } else {
            upper.merge(num, 1, Integer::sum);
            upperSize++;
        }
        rebalance();
    }

    private void removeNum(int num) {
        if (lower.containsKey(num)) {
            if (lower.get(num) == 1) lower.remove(num);
            else lower.merge(num, -1, Integer::sum);
            lowerSize--;
        } else {
            if (upper.get(num) == 1) upper.remove(num);
            else upper.merge(num, -1, Integer::sum);
            upperSize--;
        }
        rebalance();
    }

    private void rebalance() {
        while (lowerSize > upperSize + 1) {
            int maxLower = lower.lastKey();
            if (lower.get(maxLower) == 1) lower.remove(maxLower);
            else lower.merge(maxLower, -1, Integer::sum);
            upper.merge(maxLower, 1, Integer::sum);
            lowerSize--;
            upperSize++;
        }
        while (upperSize > lowerSize) {
            int minUpper = upper.firstKey();
            if (upper.get(minUpper) == 1) upper.remove(minUpper);
            else upper.merge(minUpper, -1, Integer::sum);
            lower.merge(minUpper, 1, Integer::sum);
            upperSize--;
            lowerSize++;
        }
    }

    private double getMedian(int k) {
        if (k % 2 == 1) return lower.lastKey();
        return ((long) lower.lastKey() + upper.firstKey()) / 2.0;
    }
}
```

### Complexity
- **Per window slide**: O(log k)
- **Total**: O(n log k)
- **Space**: O(k)

### Variants
- Use two `TreeMap<Integer, Integer>` (value -> count) for duplicates
- Alternative: Sorted list with binary search insert/remove = O(k) per op
- For integers in small range: Segment tree / BIT on value range

---

## Pattern 3: Moving Average from Data Stream

### Signal
- Fixed window size
- Simple aggregate (sum, average)
- FIFO behavior

### Visualization

```
Window size = 3

Stream: 1, 10, 3, 5, 8

  Queue state       Sum    Average
  [1]               1      1.0
  [1,10]            11     5.5
  [1,10,3]          14     4.67
  [10,3,5]          18     6.0     ← 1 evicted
  [3,5,8]           16     5.33    ← 10 evicted

Circular buffer (no allocation):
  ┌───┬───┬───┐
  │ 3 │ 5 │ 8 │   index = count % size
  └───┴───┴───┘
    0   1   2
```

### Template (Java)

```java
class MovingAverage {
    int[] window;
    int head = 0, count = 0;
    long sum = 0;

    public MovingAverage(int size) {
        window = new int[size];
    }

    public double next(int val) {
        if (count >= window.length) {
            sum -= window[head]; // evict oldest
        }
        window[head] = val;
        sum += val;
        head = (head + 1) % window.length;
        count++;
        return (double) sum / Math.min(count, window.length);
    }
}
```

### Complexity
- **next()**: O(1)
- **Space**: O(window size)

### Variants
- Moving max/min: Use monotonic deque (Pattern: Sliding Window Maximum)
- Exponential moving average: `ema = alpha * new + (1-alpha) * ema` (O(1) space)

---

## Pattern 4: Kth Largest Element in a Stream

### Signal
- Stream of numbers, query "what is the kth largest right now?"
- Only care about top-k, discard everything else

### Visualization

```
k = 3, stream: 4, 5, 8, 2, 3, 10

  Min-heap (size k)     kth largest (= heap top)
  [4]                   4 (size < k, partial)
  [4,5]                 4 (size < k, partial)
  [4,5,8]              4
  [4,5,8] skip 2       4   (2 < 4, ignore)
  [4,5,8] skip 3       4   (3 < 4, ignore)
  [5,8,10]             5   (10 > 4, replace 4)

Invariant: heap contains k largest elements seen so far
           heap.peek() = kth largest
```

### Template (Java)

```java
class KthLargest {
    PriorityQueue<Integer> minHeap = new PriorityQueue<>();
    int k;

    public KthLargest(int k, int[] nums) {
        this.k = k;
        for (int n : nums) add(n);
    }

    public int add(int val) {
        minHeap.offer(val);
        if (minHeap.size() > k) {
            minHeap.poll(); // evict smallest, keep only k largest
        }
        return minHeap.peek();
    }
}
```

### Complexity
- **add()**: O(log k)
- **Space**: O(k)

### Variants
- Kth smallest: use max-heap of size k
- If k changes dynamically: use two heaps (like median finder generalized)

---

## Pattern 5: Design Stock Price System

### Signal
- Timestamped updates (can correct past prices)
- Queries: current price, max price, min price, at timestamp

### Visualization

```
Operations:
  update(1, 10), update(2, 5), update(1, 3), current(), max(), min()

  timestamps: {1: 3, 2: 5}  (corrected ts=1 from 10 to 3)
  maxTimestamp = 2 → current = 5
  sorted prices: TreeMap or heap tracking all active prices
  max = 5, min = 3
```

### Template (Java)

```java
class StockPrice {
    Map<Integer, Integer> timestampToPrice = new HashMap<>();
    TreeMap<Integer, Integer> priceCount = new TreeMap<>(); // price -> frequency
    int maxTimestamp = 0;

    public void update(int timestamp, int price) {
        maxTimestamp = Math.max(maxTimestamp, timestamp);

        if (timestampToPrice.containsKey(timestamp)) {
            int oldPrice = timestampToPrice.get(timestamp);
            int cnt = priceCount.get(oldPrice);
            if (cnt == 1) priceCount.remove(oldPrice);
            else priceCount.put(oldPrice, cnt - 1);
        }

        timestampToPrice.put(timestamp, price);
        priceCount.merge(price, 1, Integer::sum);
    }

    public int current() {
        return timestampToPrice.get(maxTimestamp);
    }

    public int maximum() {
        return priceCount.lastKey();
    }

    public int minimum() {
        return priceCount.firstKey();
    }
}
```

### Complexity
- **update**: O(log n) — TreeMap operations
- **current/max/min**: O(log n)
- **Space**: O(n)

### Variants
- If only current + max + min (no corrections): two heaps + lazy deletion
- With time-range queries: augmented BST or segment tree on timestamps

---

## Pattern 6: Online Majority Element (Boyer-Moore in Stream)

### Signal
- Element appearing > n/2 times (guaranteed to exist)
- Single pass, O(1) space
- "Heavy hitter" detection

### Visualization

```
Stream: 2, 2, 1, 1, 1, 2, 2

  candidate  count
  2          1
  2          2
  2          1  (1 cancels one 2)
  2          0  (1 cancels another)
  1          1  (new candidate)
  1          0  (2 cancels)
  2          1  ← final candidate = 2

Intuition: majority element survives all cancellations
           because it has > n/2 occurrences
```

### Template (Java)

```java
class MajorityVote {
    int candidate = 0, count = 0;

    // Call for each element in stream
    public void process(int num) {
        if (count == 0) {
            candidate = num;
            count = 1;
        } else if (num == candidate) {
            count++;
        } else {
            count--;
        }
    }

    public int getCandidate() {
        return candidate; // only valid if majority guaranteed
    }

    // If majority NOT guaranteed, need verification pass
    // (impossible in single-pass stream without storing data)
}
```

### Complexity
- **Per element**: O(1)
- **Space**: O(1)

### Variants
- Top-2 candidates (elements > n/3): maintain 2 candidate-count pairs
- General top-k (> n/(k+1)): k candidate-count pairs (Misra-Gries algorithm)
- **Caveat**: Must verify candidate if majority not guaranteed (requires 2nd pass)

---

## Pattern 7: First Unique Character in Stream

### Signal
- Characters arrive one by one
- Query: "What is the first non-repeating character so far?"
- Need to track order AND frequency

### Visualization

```
Stream: a, b, c, b, a, d

  State after each char:
  'a': unique=[a], freq={a:1}         → first unique = 'a'
  'b': unique=[a,b], freq={a:1,b:1}   → first unique = 'a'
  'c': unique=[a,b,c]                  → first unique = 'a'
  'b': unique=[a,c], freq={b:2}        → first unique = 'a'  (b removed)
  'a': unique=[c], freq={a:2}          → first unique = 'c'  (a removed)
  'd': unique=[c,d]                    → first unique = 'c'

  LinkedHashMap maintains insertion order + O(1) removal
```

### Template (Java)

```java
class FirstUnique {
    Map<Character, Integer> freq = new HashMap<>();
    LinkedHashMap<Character, Boolean> order = new LinkedHashMap<>();

    public void add(char c) {
        freq.merge(c, 1, Integer::sum);
        if (freq.get(c) == 1) {
            order.put(c, true);
        } else {
            order.remove(c);
        }
    }

    public char firstUnique() {
        if (order.isEmpty()) return ' ';
        return order.entrySet().iterator().next().getKey();
    }
}

// Alternative: Queue + HashSet for seen/duplicate tracking
class FirstUniqueQueue {
    Queue<Character> queue = new LinkedList<>();
    Map<Character, Integer> freq = new HashMap<>();

    public void add(char c) {
        freq.merge(c, 1, Integer::sum);
        queue.offer(c);
    }

    public char firstUnique() {
        while (!queue.isEmpty() && freq.get(queue.peek()) > 1) {
            queue.poll(); // lazy removal
        }
        return queue.isEmpty() ? ' ' : queue.peek();
    }
}
```

### Complexity
- **add**: O(1)
- **firstUnique**: O(1) amortized (each element polled at most once)
- **Space**: O(n) worst case, O(alphabet) if bounded charset

---

## Pattern 8: Stream of Characters (Suffix Trie Matching)

### Signal
- Characters arrive one at a time
- Query: "Does any suffix of the stream so far match a word in dictionary?"
- Reversed trie approach

### Visualization

```
Words: ["cd", "f", "kl"]
Stream: a, b, c, d, ...

After 'd': stream = "abcd"
  Check suffixes: "d", "cd", "bcd", "abcd"
  "cd" matches! → return true

Key insight: Build trie of REVERSED words
  "cd" → insert "dc" into trie
  "f"  → insert "f"
  "kl" → insert "lk"

On query, traverse trie with stream chars in reverse order
(keep stream buffer or just last maxWordLen chars)
```

### Template (Java)

```java
class StreamChecker {
    int[][] trie;
    boolean[] isEnd;
    int trieIdx = 0;
    int maxLen = 0;
    StringBuilder stream = new StringBuilder();

    public StreamChecker(String[] words) {
        trie = new int[25001 * 26][26]; // adjust size
        isEnd = new boolean[25001 * 26];

        for (String word : words) {
            maxLen = Math.max(maxLen, word.length());
            int node = 0;
            // Insert reversed word
            for (int i = word.length() - 1; i >= 0; i--) {
                int c = word.charAt(i) - 'a';
                if (trie[node][c] == 0) {
                    trie[node][c] = ++trieIdx;
                }
                node = trie[node][c];
            }
            isEnd[node] = true;
        }
    }

    public boolean query(char letter) {
        stream.append(letter);
        int node = 0;
        // Search trie with stream in reverse
        for (int i = stream.length() - 1;
             i >= Math.max(0, stream.length() - maxLen); i--) {
            int c = stream.charAt(i) - 'a';
            if (trie[node][c] == 0) return false;
            node = trie[node][c];
            if (isEnd[node]) return true;
        }
        return false;
    }
}
```

### Complexity
- **Build**: O(sum of word lengths)
- **query()**: O(maxWordLength)
- **Space**: O(total chars in all words * 26) for trie

### Variants
- Aho-Corasick automaton for multi-pattern matching in stream (O(1) per char amortized)
- If words are short and few: rolling hash / KMP per word

---

## Pattern 9: Logger Rate Limiter

### Signal
- Messages with timestamps
- "Should this message be printed?" (not if printed in last N seconds)
- Simplest stream dedup with TTL

### Visualization

```
shouldPrint("foo", 1) → true   (first time)
shouldPrint("bar", 2) → true
shouldPrint("foo", 3) → false  (1+10 > 3, within cooldown)
shouldPrint("foo", 11)→ true   (1+10 <= 11, cooldown expired)

HashMap: message → last_printed_timestamp
```

### Template (Java)

```java
class Logger {
    Map<String, Integer> lastPrinted = new HashMap<>();
    static final int COOLDOWN = 10;

    public boolean shouldPrintMessage(int timestamp, String message) {
        if (!lastPrinted.containsKey(message) ||
            timestamp - lastPrinted.get(message) >= COOLDOWN) {
            lastPrinted.put(message, timestamp);
            return true;
        }
        return false;
    }
}

// Memory-bounded variant: evict old entries
class LoggerBounded {
    LinkedHashMap<String, Integer> cache;

    public LoggerBounded(int maxSize) {
        cache = new LinkedHashMap<>(maxSize, 0.75f, true) {
            protected boolean removeEldestEntry(Map.Entry eldest) {
                return size() > maxSize;
            }
        };
    }

    public boolean shouldPrintMessage(int timestamp, String message) {
        Integer last = cache.get(message);
        if (last == null || timestamp - last >= 10) {
            cache.put(message, timestamp);
            return true;
        }
        return false;
    }
}
```

### Complexity
- **shouldPrint**: O(1) average
- **Space**: O(number of unique messages) — unbounded without eviction!

### Variants
- Sliding window rate limiter: Queue of timestamps per key
- Token bucket / leaky bucket for actual rate limiting (system design)
- If memory concern: use TTL cache or periodic cleanup

---

## Pattern 10: Design Leaderboard

### Signal
- Players submit scores (additive or replace)
- Queries: top K scores, player rank, reset player

### Visualization

```
addScore("alice", 50), addScore("bob", 30), addScore("alice", 20)
Scores: {alice: 70, bob: 30}
top(1) → 70
top(2) → 100 (70 + 30)
reset("alice")
Scores: {bob: 30}

TreeMap<Integer, Integer> (score → count) for O(log n) top-K
HashMap<String, Integer> (player → score) for O(1) lookup
```

### Template (Java)

```java
class Leaderboard {
    Map<String, Integer> playerScore = new HashMap<>();
    TreeMap<Integer, Integer> scoreCount = new TreeMap<>(Collections.reverseOrder());

    public void addScore(String playerId, int score) {
        if (playerScore.containsKey(playerId)) {
            int old = playerScore.get(playerId);
            decrementScore(old);
            playerScore.put(playerId, old + score);
            incrementScore(old + score);
        } else {
            playerScore.put(playerId, score);
            incrementScore(score);
        }
    }

    public int top(int K) {
        int sum = 0, remaining = K;
        for (var entry : scoreCount.entrySet()) {
            int score = entry.getKey();
            int count = entry.getValue();
            int take = Math.min(remaining, count);
            sum += score * take;
            remaining -= take;
            if (remaining == 0) break;
        }
        return sum;
    }

    public void reset(String playerId) {
        int score = playerScore.remove(playerId);
        decrementScore(score);
    }

    private void incrementScore(int score) {
        scoreCount.merge(score, 1, Integer::sum);
    }

    private void decrementScore(int score) {
        int cnt = scoreCount.get(score);
        if (cnt == 1) scoreCount.remove(score);
        else scoreCount.put(score, cnt - 1);
    }
}
```

### Complexity
- **addScore / reset**: O(log n)
- **top(K)**: O(K) worst case (iterate top scores)
- **Space**: O(n)

### Variants
- If scores update rarely but top-K queried often: maintain sorted array
- Real-time ranking with millions of players: bucket sort by score ranges + segment tree

---

## Pattern 11: Top K Frequent Elements in Stream

### Signal
- Elements arrive continuously
- Query: "What are the K most frequent elements?"
- Trade-off: exact vs approximate

### Visualization

```
Stream: 1, 1, 2, 2, 2, 3, 1, 1

Frequency map: {1:4, 2:3, 3:1}

Approach 1: HashMap + Min-Heap of size K
  Heap keeps K most frequent by (freq, element)
  Rebuild on query: O(n log k)

Approach 2: HashMap + Bucket Sort
  Buckets by frequency:
  freq 1: [3]
  freq 2: []
  freq 3: [2]
  freq 4: [1]
  Scan from highest bucket → collect K elements: O(n) setup, O(n) query

Approach 3 (Approximate): Space-Saving Algorithm
  Maintain k counters, evict minimum when full
```

### Template (Java)

```java
// Exact: HashMap + Bucket Sort (best for periodic top-K queries)
class TopKFrequent {
    Map<Integer, Integer> freq = new HashMap<>();
    int maxFreq = 0;

    public void add(int num) {
        freq.merge(num, 1, Integer::sum);
        maxFreq = Math.max(maxFreq, freq.get(num));
    }

    @SuppressWarnings("unchecked")
    public List<Integer> topK(int k) {
        // Bucket sort by frequency
        List<Integer>[] buckets = new List[maxFreq + 1];
        for (var entry : freq.entrySet()) {
            int f = entry.getValue();
            if (buckets[f] == null) buckets[f] = new ArrayList<>();
            buckets[f].add(entry.getKey());
        }

        List<Integer> result = new ArrayList<>();
        for (int i = maxFreq; i >= 0 && result.size() < k; i--) {
            if (buckets[i] != null) {
                result.addAll(buckets[i]);
            }
        }
        return result.subList(0, Math.min(k, result.size()));
    }
}

// Heap approach (better when K << N and query is infrequent)
class TopKHeap {
    Map<Integer, Integer> freq = new HashMap<>();

    public void add(int num) {
        freq.merge(num, 1, Integer::sum);
    }

    public List<Integer> topK(int k) {
        PriorityQueue<Integer> minHeap =
            new PriorityQueue<>((a, b) -> freq.get(a) - freq.get(b));

        for (int key : freq.keySet()) {
            minHeap.offer(key);
            if (minHeap.size() > k) minHeap.poll();
        }

        List<Integer> result = new ArrayList<>(minHeap);
        Collections.reverse(result);
        return result;
    }
}
```

### Complexity

| Approach | add() | topK() | Space |
|----------|-------|--------|-------|
| HashMap + Bucket | O(1) | O(n) rebuild | O(n) |
| HashMap + Heap | O(1) | O(n log k) | O(n) |
| Space-Saving (approx) | O(1) | O(k log k) | O(k) |

---

## Pattern 12: Probabilistic Structures (Count-Min Sketch / HyperLogLog)

### Signal
- Massive streams (millions/billions of elements)
- Exact counting infeasible (space constraint)
- Acceptable error margin (system design context)
- "Approximately how many times?", "Approximately how many distinct?"

### Count-Min Sketch

```
Purpose: Approximate frequency of any element
Trade-off: Always OVER-counts, never under-counts

Structure: d hash functions, w buckets each (d x w matrix)

    h1: [ 0 | 3 | 0 | 1 | 0 | 2 ]
    h2: [ 1 | 0 | 4 | 0 | 0 | 1 ]
    h3: [ 0 | 0 | 2 | 0 | 3 | 0 ]

Insert "x": increment h1(x), h2(x), h3(x)
Query "x":  return MIN(h1(x), h2(x), h3(x))

Parameters:
  w = ceil(e / epsilon)      → controls error
  d = ceil(ln(1 / delta))    → controls confidence
  epsilon = 0.01, delta = 0.01 → w=272, d=5 (tiny memory!)
```

```java
class CountMinSketch {
    int[][] table;
    int width, depth;
    int[] hashA, hashB; // hash function parameters

    public CountMinSketch(double epsilon, double delta) {
        this.width = (int) Math.ceil(Math.E / epsilon);
        this.depth = (int) Math.ceil(Math.log(1.0 / delta));
        table = new int[depth][width];
        Random rand = new Random();
        hashA = new int[depth];
        hashB = new int[depth];
        for (int i = 0; i < depth; i++) {
            hashA[i] = rand.nextInt(Integer.MAX_VALUE) + 1;
            hashB[i] = rand.nextInt(Integer.MAX_VALUE);
        }
    }

    private int hash(int item, int i) {
        return Math.floorMod((long) hashA[i] * item + hashB[i], width);
    }

    public void add(int item) {
        for (int i = 0; i < depth; i++) {
            table[i][hash(item, i)]++;
        }
    }

    public int estimate(int item) {
        int min = Integer.MAX_VALUE;
        for (int i = 0; i < depth; i++) {
            min = Math.min(min, table[i][hash(item, i)]);
        }
        return min;
    }
}
```

### HyperLogLog

```
Purpose: Approximate COUNT DISTINCT (cardinality)
Space: ~1.5 KB for ~2% error on billions of elements

Intuition: Hash each element. Count leading zeros in hash.
  More leading zeros observed → higher cardinality likely.

  hash("cat") = 0001...  → 3 leading zeros
  hash("dog") = 0000001... → 6 leading zeros
  Seeing 6 leading zeros suggests ~2^6 = 64 distinct elements

Practical: Split into m=2^b registers (buckets)
  Each register stores max leading zeros seen
  Harmonic mean across registers → cardinality estimate

  Error ≈ 1.04 / sqrt(m)
  m=1024 → ~3.2% error, uses 1KB
  m=16384 → ~0.8% error, uses 12KB (Redis default)
```

```java
// Conceptual implementation (production: use Redis PFADD/PFCOUNT)
class HyperLogLog {
    int[] registers;
    int m; // number of registers = 2^b
    int b; // bits for bucket index

    public HyperLogLog(int b) {
        this.b = b;
        this.m = 1 << b;
        registers = new int[m];
    }

    public void add(Object item) {
        long hash = hash64(item);
        int bucket = (int) (hash >>> (64 - b)); // first b bits
        long remaining = hash << b;              // remaining bits
        int leadingZeros = Long.numberOfLeadingZeros(remaining) + 1;
        registers[bucket] = Math.max(registers[bucket], leadingZeros);
    }

    public long cardinality() {
        double harmonicMean = 0;
        for (int reg : registers) {
            harmonicMean += Math.pow(2, -reg);
        }
        double alpha = 0.7213 / (1 + 1.079 / m); // bias correction
        double estimate = alpha * m * m / harmonicMean;
        // Small/large range corrections omitted for brevity
        return (long) estimate;
    }

    private long hash64(Object item) {
        // Use MurmurHash3 or similar
        return item.hashCode() * 0x9E3779B97F4A7C15L;
    }
}
```

### Comparison Table

| Structure | Answers | Space | Error | Use Case |
|-----------|---------|-------|-------|----------|
| Count-Min Sketch | freq(x) | O(1/eps * ln(1/delta)) | +eps*N | Trending topics, heavy hitters |
| HyperLogLog | count distinct | O(m) ≈ 12KB | ~2% | Unique visitors, cardinality |
| Bloom Filter | "seen x?" | O(n/ln2) bits | False positive only | Dedup, cache lookup |
| Reservoir Sampling | uniform sample | O(k) | Exact sample | Random sampling from stream |

---

## Space-Accuracy Tradeoff Spectrum

```
                EXACT                           APPROXIMATE
    ←─────────────────────────────────────────────────────────→
    HashMap     TreeMap     Sampling     Count-Min    HyperLogLog
    O(n)        O(n)        O(k)         O(1/eps^2)   O(log log n)
    Perfect     Perfect     Unbiased     Overcount    ±2% error
                            subset       by eps*N

    Use when:   Use when:   Use when:    Use when:    Use when:
    n fits in   need order  need subset  n too large  only need
    memory      + removal   not all      for exact    cardinality
```

---

## Online vs Offline Summary

| Aspect | Online | Offline |
|--------|--------|---------|
| Data access | Single pass, element by element | Full dataset available |
| Answer availability | After each element | Only after processing all |
| Space | Must be bounded (often O(1) or O(k)) | Can use O(n) |
| Examples | Median finder, Boyer-Moore | QuickSelect, sorting |
| Competitive ratio | May not achieve optimal | Always optimal |

---

## Master Pattern Recognition Table

| Problem Signal | Pattern | Core Structure |
|----------------|---------|----------------|
| "Median" + "stream" | Two Heaps | MaxHeap + MinHeap |
| "Median" + "window" | Sorted Multiset | Two TreeMaps |
| "Average" + "last k" | Circular Buffer | Array + pointer |
| "Kth largest" + "stream" | Size-K Heap | MinHeap |
| "Timestamp corrections" + "min/max" | TreeMap counting | TreeMap<value, count> |
| "Majority" + "single pass" | Boyer-Moore | candidate + counter |
| "First unique" + "stream" | Order-preserving dedup | LinkedHashMap / Queue |
| "Pattern match" + "stream chars" | Reversed Trie | Trie of reversed words |
| "Rate limit" / "cooldown" | Timestamp map | HashMap<key, lastTime> |
| "Leaderboard" / "top scores" | Sorted counting | HashMap + TreeMap |
| "Top K frequent" | Freq map + selection | HashMap + Bucket/Heap |
| "Billions of elements" | Probabilistic | CMS / HLL / Bloom |
