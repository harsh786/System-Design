# Pattern 41: Ordered Set (TreeMap / TreeSet)

## Core Signal

> "Find nearest/next/previous element", "maintain sorted order with dynamic insertions/deletions",
> "range queries on keys", "find containing interval", "sliding window with order statistics"

If you need **O(log n) search + O(log n) insert/delete + ordered iteration**, you need a balanced BST
backed structure: `TreeMap<K,V>` or `TreeSet<E>`.

---

## Decision Flowchart

```
Need key-value lookup?
├─ Yes: Need ordered keys / range queries / nearest key?
│   ├─ Yes → TreeMap
│   └─ No  → HashMap
└─ No (set membership only):
    Need ordered elements / range queries / nearest element?
    ├─ Yes → TreeSet
    └─ No  → HashSet

Within TreeMap/TreeSet, ask:
┌─────────────────────────────────────────────────────────┐
│ "Find the largest key ≤ x"       → floorKey / floor     │
│ "Find the smallest key ≥ x"     → ceilingKey / ceiling  │
│ "Find the largest key < x"      → lowerKey / lower      │
│ "Find the smallest key > x"     → higherKey / higher    │
│ "All keys in [lo, hi]"          → subMap(lo, true, hi, true) │
│ "All keys < hi"                 → headMap(hi, false)    │
│ "All keys ≥ lo"                 → tailMap(lo, true)     │
│ "Remove and return min/max"     → pollFirstEntry / pollLastEntry │
└─────────────────────────────────────────────────────────┘
```

---

## TreeMap vs HashMap Decision Table

| Criterion | HashMap | TreeMap |
|-----------|---------|---------|
| Get/Put/Remove | O(1) avg | O(log n) |
| Ordered iteration | No | Yes (by key) |
| Range queries (subMap) | No | O(log n + k) |
| Floor/Ceiling (nearest) | No | O(log n) |
| Min/Max key | O(n) | O(log n) |
| Memory overhead | Lower | Higher (tree nodes) |
| Null keys | 1 allowed | Not allowed (needs Comparable) |
| Thread-safe variant | ConcurrentHashMap | ConcurrentSkipListMap |

**Rule of thumb**: If you ever call `floorKey`, `ceilingKey`, `subMap`, or need sorted order — TreeMap. Otherwise HashMap.

---

## Java NavigableMap / NavigableSet Method Reference

### TreeMap<K, V> (implements NavigableMap)

```java
// Nearest key queries
K floorKey(K key)           // largest key ≤ key, or null
K ceilingKey(K key)         // smallest key ≥ key, or null
K lowerKey(K key)           // largest key < key, or null
K higherKey(K key)          // smallest key > key, or null

// Nearest entry queries
Map.Entry<K,V> floorEntry(K key)
Map.Entry<K,V> ceilingEntry(K key)
Map.Entry<K,V> lowerEntry(K key)
Map.Entry<K,V> higherEntry(K key)

// Extremes
Map.Entry<K,V> firstEntry() // min key entry
Map.Entry<K,V> lastEntry()  // max key entry
Map.Entry<K,V> pollFirstEntry() // remove & return min
Map.Entry<K,V> pollLastEntry()  // remove & return max

// Range views (backed by original map — mutations reflected)
NavigableMap<K,V> subMap(K from, boolean fromInc, K to, boolean toInc)
NavigableMap<K,V> headMap(K to, boolean inclusive)
NavigableMap<K,V> tailMap(K from, boolean inclusive)
SortedMap<K,V> subMap(K from, K to)  // [from, to)

// Descending
NavigableMap<K,V> descendingMap()
NavigableSet<K> descendingKeySet()
```

### TreeSet<E> (implements NavigableSet)

```java
E floor(E e)      // largest ≤ e
E ceiling(E e)    // smallest ≥ e
E lower(E e)      // largest < e
E higher(E e)     // smallest > e
E first()         // min
E last()          // max
E pollFirst()     // remove & return min
E pollLast()      // remove & return max

NavigableSet<E> subSet(E from, boolean fromInc, E to, boolean toInc)
NavigableSet<E> headSet(E to, boolean inclusive)
NavigableSet<E> tailSet(E from, boolean inclusive)
```

---

## Common Meta-Patterns

| Pattern | Technique | Example Problems |
|---------|-----------|-----------------|
| Find Nearest | `floorKey` / `ceilingKey` | Contains Duplicate III, Stock Ticker |
| Find Containing Interval | `floorKey(point)` then check if interval covers point | My Calendar, Interval containment |
| Sliding Window + Order | Add/remove from TreeMap as window slides | Sliding Window Median |
| Event Counting (sweep) | TreeMap as diff array, prefix sum over keys | My Calendar III, Skyline |
| Merge Adjacent | `floorKey` + `higherKey` to find neighbors | Disjoint Intervals, RangeModule |
| Patience Sort / LIS | `ceilingKey` to find next pile | Russian Doll Envelopes |
| Multi-set simulation | `TreeMap<Integer, Integer>` (value → count) | Sliding Window Median |

---

## Pattern 1: TreeMap API Mastery

### Template: MultiSet via TreeMap

```java
class TreeMapMultiSet<T extends Comparable<T>> {
    private TreeMap<T, Integer> map = new TreeMap<>();
    private int size = 0;

    public void add(T val) {
        map.merge(val, 1, Integer::sum);
        size++;
    }

    public void remove(T val) {
        int count = map.getOrDefault(val, 0);
        if (count == 0) return;
        if (count == 1) map.remove(val);
        else map.put(val, count - 1);
        size--;
    }

    public T min() { return map.firstKey(); }
    public T max() { return map.lastKey(); }
    public T floor(T val) { return map.floorKey(val); }
    public T ceiling(T val) { return map.ceilingKey(val); }
    public int size() { return size; }
}
```

---

## Pattern 2: TreeSet API Mastery

### Template: Maintaining Sorted Unique Elements with Range Queries

```java
TreeSet<Integer> set = new TreeSet<>();
set.add(10); set.add(20); set.add(30); set.add(40);

// Nearest queries
set.floor(25);    // 20 (largest ≤ 25)
set.ceiling(25);  // 30 (smallest ≥ 25)
set.lower(20);    // 10 (largest < 20)
set.higher(20);   // 30 (smallest > 20)

// Range: all elements in [15, 35]
NavigableSet<Integer> range = set.subSet(15, true, 35, true); // {20, 30}

// Iteration in sorted order
for (int x : set) { /* 10, 20, 30, 40 */ }

// Descending
for (int x : set.descendingSet()) { /* 40, 30, 20, 10 */ }
```

---

## Pattern 3: My Calendar I / II / III

### Signal
"Book an event [start, end). Return true if no double/triple booking."

### My Calendar I — No Overlaps Allowed

```java
class MyCalendar {
    // Key = start, Value = end
    TreeMap<Integer, Integer> calendar = new TreeMap<>();

    public boolean book(int start, int end) {
        // Find the event that starts at or before 'start'
        Integer prev = calendar.floorKey(start);
        if (prev != null && calendar.get(prev) > start) return false;

        // Find the event that starts at or after 'start'
        Integer next = calendar.ceilingKey(start);
        if (next != null && next < end) return false;

        calendar.put(start, end);
        return true;
    }
}
```

### Visualization (My Calendar I)

```
Timeline:  ----[===A===]--------[===B===]----
                10     20        40     50

book(25, 35)?
  floorKey(25) = 10, calendar.get(10) = 20 → 20 > 25? No ✓
  ceilingKey(25) = 40 → 40 < 35? No ✓
  → Book succeeds

book(15, 25)?
  floorKey(15) = 10, calendar.get(10) = 20 → 20 > 15? Yes ✗
  → Overlap with A, reject
```

### My Calendar III — Count Max Overlapping Events

```java
class MyCalendarThree {
    // Sweep line: store +1 at start, -1 at end
    TreeMap<Integer, Integer> diff = new TreeMap<>();

    public int book(int start, int end) {
        diff.merge(start, 1, Integer::sum);
        diff.merge(end, -1, Integer::sum);

        int maxOverlap = 0, active = 0;
        for (int delta : diff.values()) {
            active += delta;
            maxOverlap = Math.max(maxOverlap, active);
        }
        return maxOverlap;
    }
}
```

### Visualization (My Calendar III)

```
Events: [10,20), [15,25), [20,30)

diff map: {10:+1, 15:+1, 20:+1-1=0, 25:-1, 30:-1}
  Actually: {10:1, 15:1, 20:0, 25:-1, 30:-1}
  Wait — let's be precise:

  After booking [10,20): diff = {10:1, 20:-1}
  After booking [15,25): diff = {10:1, 15:1, 20:-1, 25:-1}
  After booking [20,30): diff = {10:1, 15:1, 20:-1+1=0, 25:-1, 30:-1}

  Prefix sums: 10→1, 15→2, 20→2, 25→1, 30→0
  Max overlap = 2
```

### Complexity
- My Calendar I: O(log n) per book
- My Calendar III: O(n) per book (scanning all diffs)

---

## Pattern 4: Containment / Interval Overlap with TreeMap

### Signal
"Given a point, find which interval contains it" or "check if new interval overlaps existing ones."

### Template: Interval Containment Check

```java
// TreeMap: start → end (non-overlapping intervals)
TreeMap<Integer, Integer> intervals = new TreeMap<>();

boolean contains(int point) {
    Integer start = intervals.floorKey(point);
    if (start == null) return false;
    return intervals.get(start) >= point; // end >= point
}

// Find all overlapping intervals with [qStart, qEnd)
List<int[]> findOverlaps(int qStart, int qEnd) {
    List<int[]> result = new ArrayList<>();
    // Start from the interval that could overlap (starts before qEnd)
    Integer key = intervals.lowerKey(qEnd);
    while (key != null && intervals.get(key) > qStart) {
        result.add(new int[]{key, intervals.get(key)});
        key = intervals.lowerKey(key);
    }
    return result;
}
```

### Visualization

```
Intervals stored: [2,5], [8,12], [15,20]
TreeMap: {2→5, 8→12, 15→20}

Query: contains(10)?
  floorKey(10) = 8
  intervals.get(8) = 12 ≥ 10? Yes → contained in [8,12]

Query: contains(6)?
  floorKey(6) = 2
  intervals.get(2) = 5 ≥ 6? No → not contained
```

### Application: RangeModule (LC 715)

```java
class RangeModule {
    TreeMap<Integer, Integer> map = new TreeMap<>(); // start → end

    public void addRange(int left, int right) {
        Integer start = map.floorKey(left);
        Integer end = map.floorKey(right);

        if (start != null && map.get(start) >= left) {
            left = start;
        }
        if (end != null && map.get(end) > right) {
            right = map.get(end);
        }

        // Remove all intervals between left and right
        map.subMap(left, true, right, true).clear();
        map.put(left, right);
    }

    public boolean queryRange(int left, int right) {
        Integer start = map.floorKey(left);
        return start != null && map.get(start) >= right;
    }

    public void removeRange(int left, int right) {
        Integer start = map.floorKey(left);
        Integer end = map.floorKey(right);

        if (end != null && map.get(end) > right) {
            map.put(right, map.get(end));
        }
        if (start != null && map.get(start) > left) {
            map.put(start, left);
        }

        map.subMap(left, true, right, false).clear();
    }
}
```

---

## Pattern 5: Sliding Window with TreeMap

### Signal
"Find median/min/max in a sliding window" or "check condition within window using sorted order."

### Sliding Window Median (LC 480)

```java
public double[] medianSlidingWindow(int[] nums, int k) {
    TreeMap<Integer, Integer> lower = new TreeMap<>(Collections.reverseOrder()); // max-heap sim
    TreeMap<Integer, Integer> upper = new TreeMap<>(); // min-heap sim
    int lowerSize = 0, upperSize = 0;
    double[] result = new double[nums.length - k + 1];

    // Simpler approach: use two TreeMaps as multisets
    // But cleaner: single TreeMap multiset with size tracking

    // Cleaner approach for interview:
    Comparator<Integer> cmp = (a, b) -> nums[a] != nums[b] ?
        Integer.compare(nums[a], nums[b]) : Integer.compare(a, b);
    TreeSet<Integer> lo = new TreeSet<>(cmp); // lower half (indices)
    TreeSet<Integer> hi = new TreeSet<>(cmp); // upper half (indices)

    for (int i = 0; i < nums.length; i++) {
        // Add to appropriate half
        lo.add(i);
        hi.add(lo.pollLast());
        if (hi.size() > lo.size()) lo.add(hi.pollFirst());

        // Window full
        if (i >= k - 1) {
            // Compute median
            if (k % 2 == 1) {
                result[i - k + 1] = nums[lo.last()];
            } else {
                result[i - k + 1] = ((long)nums[lo.last()] + nums[hi.first()]) / 2.0;
            }
            // Remove outgoing element
            int out = i - k + 1;
            if (!lo.remove(out)) hi.remove(out);
            // Rebalance
            if (lo.size() < hi.size()) lo.add(hi.pollFirst());
            else if (lo.size() > hi.size() + 1) hi.add(lo.pollLast());
        }
    }
    return result;
}
```

### Contains Duplicate III (LC 220)

> "Find indices i,j where |i-j| <= indexDiff and |nums[i]-nums[j]| <= valueDiff"

```java
public boolean containsNearbyAlmostDuplicate(int[] nums, int indexDiff, int valueDiff) {
    TreeSet<Long> window = new TreeSet<>();

    for (int i = 0; i < nums.length; i++) {
        long val = (long) nums[i];

        // Find closest value in window that is ≥ (val - valueDiff)
        Long ceiling = window.ceiling(val - valueDiff);
        if (ceiling != null && ceiling <= val + valueDiff) {
            return true;
        }

        window.add(val);
        if (i >= indexDiff) {
            window.remove((long) nums[i - indexDiff]);
        }
    }
    return false;
}
```

### Visualization (Contains Duplicate III)

```
nums = [1, 5, 9, 1, 5, 9], indexDiff = 2, valueDiff = 3

i=0: window={1}, no match
i=1: ceiling(5-3)=ceiling(2)→5, 5<=8? Yes? Wait, window={1,5}
     ceiling(2) from {1,5} = 5. Is 5 <= 5+3=8? Yes → but check:
     Actually we check before adding. window={1}. ceiling(5-3=2)=null? No wait...
     Let me redo:

i=0: window={}. ceiling(1-3=-2)=null. Add 1. window={1}
i=1: window={1}. ceiling(5-3=2)=null (no element ≥ 2 in {1}... wait 1<2). Add 5. window={1,5}
i=2: window={1,5}. ceiling(9-3=6)=null. Add 9. window={1,5,9}. Remove nums[0]=1. window={5,9}
i=3: window={5,9}. ceiling(1-3=-2)=5. 5<=1+3=4? No. Add 1. window={1,5,9}. Remove nums[1]=5. window={1,9}
i=4: window={1,9}. ceiling(5-3=2)=9. 9<=5+3=8? No. Add 5. window={1,5,9}. Remove nums[2]=9. window={1,5}
i=5: window={1,5}. ceiling(9-3=6)=null. No match.

Result: false ✓ (no pair within distance 2 has value diff ≤ 3)
```

### Complexity
- O(n log k) for both problems, where k is window size.

---

## Pattern 6: Count of Range Sum (LC 327)

### Signal
"Count subarrays with sum in [lower, upper]"

### Approach: Ordered Set on Prefix Sums

```java
public int countRangeSum(int[] nums, int lower, int upper) {
    long[] prefix = new long[nums.length + 1];
    for (int i = 0; i < nums.length; i++) {
        prefix[i + 1] = prefix[i] + nums[i];
    }

    // For each j, count i < j where lower <= prefix[j] - prefix[i] <= upper
    // i.e., prefix[j] - upper <= prefix[i] <= prefix[j] - lower

    // Using merge sort is O(n log n). TreeMap approach:
    TreeMap<Long, Integer> map = new TreeMap<>(); // prefix sum → count
    int count = 0;

    for (long p : prefix) {
        // Count prefix sums in range [p - upper, p - lower]
        Long lo = p - upper;
        Long hi = p - lower;
        // Sum counts of all keys in [lo, hi]
        for (Map.Entry<Long, Integer> e : map.subMap(lo, true, hi, true).entrySet()) {
            count += e.getValue();
        }
        map.merge(p, 1, Integer::sum);
    }
    return count;
}
// Note: This is O(n * k) worst case where k = number of keys in range.
// Merge sort approach is cleaner O(n log n). But this shows the ordered set idea.
```

### Better: BIT / Merge Sort (preferred for interviews)

The ordered set approach works but has worst-case O(n^2) when many prefix sums fall in range. Merge sort or BIT with coordinate compression gives guaranteed O(n log n).

---

## Pattern 7: Russian Doll Envelopes / LIS with TreeMap

### Signal
"Longest Increasing Subsequence" or "patience sorting"

### Template: LIS via TreeMap (Patience Sorting)

```java
// Standard LIS in O(n log n) using TreeMap as "piles"
public int lengthOfLIS(int[] nums) {
    // TreeMap: pile top value → pile index (we just need count)
    // Actually, simpler: TreeMap stores the smallest tail of all increasing
    // subsequences of each length
    TreeSet<Integer> tails = new TreeSet<>();

    for (int num : nums) {
        Integer ceiling = tails.ceiling(num);
        if (ceiling != null) tails.remove(ceiling);
        tails.add(num);
    }
    return tails.size();
}
// This is equivalent to the binary search on tails array approach.
```

### Russian Doll Envelopes (LC 354)

```java
public int maxEnvelopes(int[][] envelopes) {
    // Sort by width ascending, then height descending (for same width)
    Arrays.sort(envelopes, (a, b) -> a[0] != b[0] ? a[0] - b[0] : b[1] - a[1]);

    // LIS on heights
    // Using TreeMap approach for clarity:
    TreeMap<Integer, Integer> tails = new TreeMap<>(); // tail value → pile count (not needed, just set)
    // Actually use standard tails array + binary search (more efficient)

    int[] dp = new int[envelopes.length];
    int len = 0;
    for (int[] e : envelopes) {
        int h = e[1];
        int pos = Arrays.binarySearch(dp, 0, len, h);
        if (pos < 0) pos = -(pos + 1);
        dp[pos] = h;
        if (pos == len) len++;
    }
    return len;
}
```

### TreeMap variant for LIS with value tracking

```java
// When you need to track which elements form the LIS, or need to query
// "longest increasing subsequence ending with value ≤ x":
public int lisWithTreeMap(int[] nums) {
    // dp[i] = length of LIS ending at nums[i]
    // TreeMap: value → max LIS length ending with that value
    TreeMap<Integer, Integer> map = new TreeMap<>();

    int ans = 0;
    for (int num : nums) {
        // Find max LIS length for all values < num
        Integer prev = map.lowerKey(num);
        int len = 1;
        if (prev != null) len = map.get(prev) + 1; // BUG: need max of all keys < num

        // Actually need: max value in map for keys < num
        // TreeMap alone can't do range-max efficiently.
        // This is where a Segment Tree or BIT is better.
        // TreeMap works if we maintain: for each key, the value is the max
        // LIS length for that key AND all smaller keys (monotonic pruning).

        // Correct approach: maintain map where if key1 < key2, then val1 < val2
        // (prune dominated entries)
        // Remove all entries with key >= num and value <= len
        while (map.ceilingKey(num) != null && map.get(map.ceilingKey(num)) <= len) {
            map.remove(map.ceilingKey(num));
        }
        map.put(num, len);
        ans = Math.max(ans, len);
    }
    return ans;
}
```

---

## Pattern 8: Stock Price Fluctuation (LC 2034)

### Signal
"Update prices at timestamps, query current/max/min price"

```java
class StockPrice {
    TreeMap<Integer, Integer> timeline = new TreeMap<>(); // timestamp → price
    TreeMap<Integer, Integer> prices = new TreeMap<>();   // price → count (multiset)

    public void update(int timestamp, int price) {
        if (timeline.containsKey(timestamp)) {
            int oldPrice = timeline.get(timestamp);
            removePrice(oldPrice);
        }
        timeline.put(timestamp, price);
        prices.merge(price, 1, Integer::sum);
    }

    public int current() {
        return timeline.lastEntry().getValue();
    }

    public int maximum() {
        return prices.lastKey();
    }

    public int minimum() {
        return prices.firstKey();
    }

    private void removePrice(int price) {
        int count = prices.get(price);
        if (count == 1) prices.remove(price);
        else prices.put(price, count - 1);
    }
}
```

### Visualization

```
Operations:
  update(1, 10) → timeline: {1:10}, prices: {10:1}
  update(2, 5)  → timeline: {1:10, 2:5}, prices: {5:1, 10:1}
  current() → timeline.lastEntry() = (2,5) → 5
  maximum() → prices.lastKey() = 10
  minimum() → prices.firstKey() = 5
  update(1, 3)  → remove old price 10, add 3
                → timeline: {1:3, 2:5}, prices: {3:1, 5:1}
  maximum() → 5
  minimum() → 3
```

### Complexity
- All operations: O(log n)

---

## Pattern 9: Intervals Management (Add/Remove)

### Signal
"Add intervals, remove intervals, query if a range is covered."

### Template: Non-overlapping Intervals Maintenance

```java
class IntervalManager {
    TreeMap<Integer, Integer> map = new TreeMap<>(); // start → end

    // Add [start, end), merging overlaps
    void add(int start, int end) {
        // Expand left: check if previous interval overlaps
        Integer lo = map.floorKey(start);
        if (lo != null && map.get(lo) >= start) {
            start = lo;
            end = Math.max(end, map.get(lo));
        }

        // Expand right: merge all overlapping intervals
        while (true) {
            Integer hi = map.higherKey(start);
            if (hi != null && hi <= end) {
                end = Math.max(end, map.get(hi));
                map.remove(hi);
            } else {
                break;
            }
        }

        // Remove the floor entry if it was merged
        if (lo != null && map.get(lo) != null && lo >= start) {
            map.remove(lo);
        }

        map.put(start, end);
    }

    // Remove [start, end)
    void remove(int start, int end) {
        // Same logic as RangeModule.removeRange (see Pattern 4)
        Integer lo = map.floorKey(start);
        Integer hi = map.floorKey(end);

        if (hi != null && map.get(hi) > end) {
            map.put(end, map.get(hi));
        }
        if (lo != null && map.get(lo) > start) {
            map.put(lo, start);
        }

        map.subMap(start, true, end, false).clear();
    }

    boolean covers(int point) {
        Integer lo = map.floorKey(point);
        return lo != null && map.get(lo) > point;
    }
}
```

---

## Pattern 10: Skyline Problem (LC 218)

### Signal
"Given building rectangles [left, right, height], output the skyline contour."

### Template: Sweep Line + TreeMap Max-Height

```java
public List<List<Integer>> getSkyline(int[][] buildings) {
    // Create events: (x, type, height)
    // Start: height added, End: height removed
    List<int[]> events = new ArrayList<>();
    for (int[] b : buildings) {
        events.add(new int[]{b[0], -b[2]}); // start: negative height (process starts first)
        events.add(new int[]{b[1], b[2]});   // end: positive height
    }
    // Sort by x, then by height (negative = start processed first at same x)
    events.sort((a, b) -> a[0] != b[0] ? a[0] - b[0] : a[1] - b[1]);

    // TreeMap as max-height multiset
    TreeMap<Integer, Integer> heights = new TreeMap<>();
    heights.put(0, 1); // ground level
    int prevMax = 0;
    List<List<Integer>> result = new ArrayList<>();

    for (int[] event : events) {
        int x = event[0], h = Math.abs(event[1]);

        if (event[1] < 0) {
            // Building starts
            heights.merge(h, 1, Integer::sum);
        } else {
            // Building ends
            int count = heights.get(h);
            if (count == 1) heights.remove(h);
            else heights.put(h, count - 1);
        }

        int curMax = heights.lastKey();
        if (curMax != prevMax) {
            result.add(Arrays.asList(x, curMax));
            prevMax = curMax;
        }
    }
    return result;
}
```

### Visualization

```
Buildings: [2,9,10], [3,7,15], [5,12,12]

Events sorted: (2,-10), (3,-15), (5,-12), (7,15), (9,10), (12,12)

Processing:
x=2:  add h=10.  heights={0:1, 10:1}. max=10. prev=0 → emit (2,10)
x=3:  add h=15.  heights={0:1, 10:1, 15:1}. max=15. prev=10 → emit (3,15)
x=5:  add h=12.  heights={0:1, 10:1, 12:1, 15:1}. max=15. no change
x=7:  rem h=15.  heights={0:1, 10:1, 12:1}. max=12. prev=15 → emit (7,12)
x=9:  rem h=10.  heights={0:1, 12:1}. max=12. no change
x=12: rem h=12.  heights={0:1}. max=0. prev=12 → emit (12,0)

Skyline: [(2,10), (3,15), (7,12), (12,0)]
```

### Complexity
- O(n log n): sorting events + O(log n) per TreeMap operation

---

## Pattern 11: Data Stream as Disjoint Intervals (LC 352)

### Signal
"Numbers arrive one by one. At any point, return the disjoint intervals covering all numbers seen."

```java
class SummaryRanges {
    TreeMap<Integer, Integer> map = new TreeMap<>(); // start → end

    public void addNum(int val) {
        Integer lo = map.floorKey(val);
        Integer hi = map.higherKey(val);

        // Check if val is already covered
        if (lo != null && map.get(lo) >= val) return;

        boolean mergeLeft = (lo != null && map.get(lo) == val - 1);
        boolean mergeRight = (hi != null && hi == val + 1);

        if (mergeLeft && mergeRight) {
            // Merge both: extend left interval to cover right
            map.put(lo, map.get(hi));
            map.remove(hi);
        } else if (mergeLeft) {
            // Extend left interval
            map.put(lo, val);
        } else if (mergeRight) {
            // Extend right interval to start at val
            map.put(val, map.get(hi));
            map.remove(hi);
        } else {
            // New singleton interval
            map.put(val, val);
        }
    }

    public int[][] getIntervals() {
        int[][] res = new int[map.size()][2];
        int i = 0;
        for (var e : map.entrySet()) {
            res[i++] = new int[]{e.getKey(), e.getValue()};
        }
        return res;
    }
}
```

### Visualization

```
addNum(1): map={1→1}
addNum(3): map={1→1, 3→3}
addNum(7): map={1→1, 3→3, 7→7}
addNum(2): mergeLeft(1→1, val-1=1✓) mergeRight(3==val+1=3✓) → merge both
           map={1→3, 7→7}
addNum(6): mergeRight(7==val+1=7✓) → map={1→3, 6→7}
addNum(4): lo=floorKey(4)=1, map.get(1)=3, 3==val-1=3✓ mergeLeft
           hi=higherKey(4)=6, 6==val+1=5? No
           → extend left: map={1→4, 6→7}
addNum(5): lo=floorKey(5)=1, map.get(1)=4, 4==val-1=4✓ mergeLeft
           hi=higherKey(5)=6, 6==val+1=6✓ mergeRight
           → merge both: map={1→7}

getIntervals() → [[1,7]]
```

### Complexity
- addNum: O(log n)
- getIntervals: O(n)

---

## Pattern 12: Number of Visible People in a Queue (LC 1944)

### Signal
"People in a queue, can see right if no taller person blocks. Count visible people."

This is primarily a **monotonic stack** problem, but a TreeMap variant exists for related problems (e.g., "how many people can person i see" with additional constraints).

### Monotonic Stack Solution (Primary)

```java
public int[] canSeePersonsCount(int[] heights) {
    int n = heights.length;
    int[] result = new int[n];
    Deque<Integer> stack = new ArrayDeque<>(); // monotonic decreasing

    for (int i = n - 1; i >= 0; i--) {
        int count = 0;
        // Pop all shorter people — current person can see them
        while (!stack.isEmpty() && heights[stack.peek()] < heights[i]) {
            stack.pop();
            count++;
        }
        // Can also see the next taller/equal person (top of stack)
        if (!stack.isEmpty()) count++;
        result[i] = count;
        stack.push(i);
    }
    return result;
}
```

### TreeMap Variant: "Find Rank of Next Greater" Pattern

```java
// When you need: "for each element, how many distinct values exist between
// this element and the next greater element to its right"
// TreeMap tracks elements seen so far (processing right to left)
public int[] visibleWithTreeMap(int[] heights) {
    int n = heights.length;
    int[] result = new int[n];
    TreeMap<Integer, Integer> seen = new TreeMap<>(); // height → count

    for (int i = n - 1; i >= 0; i--) {
        // All elements in (0, heights[i]) that are in 'seen' and not blocked
        // This doesn't directly solve the problem efficiently — stick with monotonic stack.
        // TreeMap variant is useful for "count elements in range" type queries.

        // For completeness: count keys in range (heights[i], ∞) gives nothing useful here.
        // This pattern is better suited for problems like "count smaller after self"
        seen.merge(heights[i], 1, Integer::sum);
    }
    return result; // Use monotonic stack above
}
```

**Note**: The monotonic stack is the canonical O(n) solution. TreeMap/ordered-set variants are more relevant for problems like "Count of Smaller Numbers After Self" (LC 315) where you need rank queries:

```java
// Count Smaller After Self — TreeMap-based (simpler but O(n log^2 n) with subMap size)
// Better with BIT/merge sort, but shows the pattern:
public List<Integer> countSmaller(int[] nums) {
    int n = nums.length;
    Integer[] result = new Integer[n];
    TreeMap<Integer, Integer> map = new TreeMap<>(); // value → count

    for (int i = n - 1; i >= 0; i--) {
        // Count elements < nums[i] in map
        int count = 0;
        for (int c : map.headMap(nums[i], false).values()) {
            count += c;
        }
        result[i] = count;
        map.merge(nums[i], 1, Integer::sum);
    }
    return Arrays.asList(result);
}
// O(n * k) worst case — use BIT with coordinate compression for O(n log n)
```

---

## Summary: When to Reach for TreeMap/TreeSet

| Problem Shape | Key Operation | Example |
|---------------|---------------|---------|
| "Is there an element within distance d of x?" | `ceiling(x-d)` check ≤ x+d | Contains Duplicate III |
| "Find the interval containing point p" | `floorKey(p)` then check end | My Calendar, RangeModule |
| "Merge overlapping intervals dynamically" | `floorKey` + `higherKey` | Disjoint Intervals |
| "Track max/min with dynamic add/remove" | `lastKey()` / `firstKey()` | Stock Price, Skyline |
| "Sweep line event counting" | TreeMap as diff array | My Calendar III |
| "Sliding window order statistics" | Add/remove as window slides | Sliding Window Median |
| "Next available slot/position" | `ceiling(x)` | Meeting Rooms, Exam Room |
| "Count in range" | `subMap(lo, hi).size()` | Count of Range Sum |

---

## Pitfalls

1. **TreeMap does NOT support duplicate keys** — use `TreeMap<K, Integer>` as a multiset (value = count).
2. **subMap/headMap/tailMap return views** — modifications to the view modify the original map. Use `new TreeMap<>(map.subMap(...))` if you need a copy.
3. **ConcurrentModificationException** — don't modify the map while iterating its views. Collect keys first, then mutate.
4. **Null returns** — `floorKey`, `ceilingKey`, etc. return `null` if no match. Always null-check.
5. **Comparator consistency** — if using custom Comparator, ensure it's consistent with equals, or `remove()` won't work as expected.
6. **Integer overflow in keys** — when using arithmetic on keys (e.g., `val - valueDiff`), cast to `long` first.

---

## Complexity Summary

| Operation | TreeMap/TreeSet | Notes |
|-----------|----------------|-------|
| put / add | O(log n) | |
| get / contains | O(log n) | |
| remove | O(log n) | |
| floorKey / ceilingKey | O(log n) | |
| firstKey / lastKey | O(log n) | |
| subMap iteration | O(log n + k) | k = elements in range |
| size() | O(1) | |
| Iteration (full) | O(n) | In sorted order |
