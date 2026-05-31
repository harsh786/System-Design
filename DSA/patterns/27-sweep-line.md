# 27 - Sweep Line / Line Sweep

## Core Concept

A **sweep line** moves across a dimension (usually x-axis or time), processing **events** at discrete points. Instead of checking all intervals against each other (O(n^2)), we decompose intervals into events, sort them, and process sequentially.

```
Timeline:  ──────────────────────────────────────────►
Events:       +1    +1    -1       +1   -1    -1
Active:        1     2     1        2    1     0
              ▲                                ▲
           sweep enters                    sweep exits
```

---

## Signal: When to Use Sweep Line

| Signal | Example |
|--------|---------|
| "Maximum/minimum overlapping intervals" | Meeting Rooms II |
| "Merge or count overlapping regions" | Merge Intervals |
| "Outline/contour of overlapping shapes" | Skyline Problem |
| "How many active at time t" | My Calendar III |
| "Capacity constraint over time" | Car Pooling |
| "Intersection of interval lists" | Interval List Intersections |

---

## Decision Flowchart

```
Is the problem about intervals/ranges on a number line?
│
├─ YES → Do you need the count of overlaps at every point?
│   ├─ YES → Are coordinates bounded & small?
│   │   ├─ YES → Difference Array
│   │   └─ NO  → TreeMap (sorted event map)
│   │
│   └─ NO → Do you need to merge/transform intervals?
│       ├─ Merge overlapping → Sort by start, greedy merge
│       ├─ Find intersections → Two-pointer on sorted lists
│       └─ Find max overlap depth → Event sort + counter
│
└─ NO → Probably not sweep line
```

### TreeMap vs PriorityQueue vs Difference Array

| Technique | When | Time | Space |
|-----------|------|------|-------|
| **Difference Array** | Coordinates bounded, integer, small range | O(n + R) | O(R) |
| **Event Sort + Counter** | Need max/min overlap, unbounded coords | O(n log n) | O(n) |
| **TreeMap** | Need dynamic overlap count, online queries | O(n log n) | O(n) |
| **PriorityQueue (max-heap)** | Need to track the "top" active element (e.g., max height) | O(n log n) | O(n) |

---

## Event Encoding Patterns

### Pattern A: +1 / -1 in same array

```java
// Encode: start → +1, end → -1
int[][] events = new int[2 * n][2];
for (int[] interval : intervals) {
    events[i++] = new int[]{interval[0], +1};  // open
    events[i++] = new int[]{interval[1], -1};  // close
}
Arrays.sort(events, (a, b) -> a[0] != b[0] ? a[0] - b[0] : a[1] - b[1]);
```

### Pattern B: TreeMap accumulation

```java
TreeMap<Integer, Integer> map = new TreeMap<>();
for (int[] interval : intervals) {
    map.merge(interval[0], +1, Integer::sum);
    map.merge(interval[1], -1, Integer::sum);
}
int active = 0, max = 0;
for (int delta : map.values()) {
    active += delta;
    max = Math.max(max, active);
}
```

### Pattern C: Difference Array (bounded)

```java
int[] diff = new int[maxCoord + 2];
for (int[] interval : intervals) {
    diff[interval[0]] += 1;
    diff[interval[1] + 1] -= 1; // +1 if end is inclusive
}
// prefix sum to get active count at each point
```

---

## Pattern 1: Event-Based Interval Processing (Meeting Rooms II)

**Problem**: Given meeting time intervals, find the minimum number of conference rooms required.

### Signal
- Overlapping intervals, need max concurrent count.

### Visualization

```
Meetings: [0,30] [5,10] [15,20]

Timeline:
0    5    10   15   20   30
|====|====|====|====|====|        Room 1: [0,30]
     |====|                       Room 2: [5,10]
               |====|             Room 2: [15,20]

Events (sorted):
  t=0  → +1  active=1
  t=5  → +1  active=2  ← max
  t=10 → -1  active=1
  t=15 → +1  active=2  ← max
  t=20 → -1  active=1
  t=30 → -1  active=0

Answer: 2
```

### Template

```java
public int minMeetingRooms(int[][] intervals) {
    int n = intervals.length;
    int[] starts = new int[n], ends = new int[n];
    for (int i = 0; i < n; i++) {
        starts[i] = intervals[i][0];
        ends[i] = intervals[i][1];
    }
    Arrays.sort(starts);
    Arrays.sort(ends);

    int rooms = 0, maxRooms = 0, endPtr = 0;
    for (int i = 0; i < n; i++) {
        if (starts[i] < ends[endPtr]) {
            rooms++;
        } else {
            endPtr++;
        }
        maxRooms = Math.max(maxRooms, rooms);
    }
    return maxRooms;
}
```

**Alternative (TreeMap)**:

```java
public int minMeetingRooms(int[][] intervals) {
    TreeMap<Integer, Integer> map = new TreeMap<>();
    for (int[] iv : intervals) {
        map.merge(iv[0], 1, Integer::sum);
        map.merge(iv[1], -1, Integer::sum);
    }
    int active = 0, max = 0;
    for (int v : map.values()) {
        active += v;
        max = Math.max(max, active);
    }
    return max;
}
```

### Complexity
- Time: O(n log n)
- Space: O(n)

---

## Pattern 2: Skyline Problem

**Problem**: Given buildings `[left, right, height]`, return the skyline contour as key points where height changes.

### Signal
- Overlapping rectangles, need the **maximum active height** at each transition point.

### Visualization

```
Buildings: [2,9,10], [3,7,15], [5,12,12]

Height profile:
15 |     ████
12 |     ████████████
10 | ████████        ████
   |___|__|__|___|___|__|___
   0   2  3  5   7   9  12

Critical points (left edge enters heap, right edge removes):
  x=2: add h=10  → max=10  → emit (2,10)
  x=3: add h=15  → max=15  → emit (3,15)
  x=5: add h=12  → max=15  → no change
  x=7: remove h=15 → max=12 → emit (7,12)
  x=9: remove h=10 → max=12 → no change
  x=12: remove h=12 → max=0  → emit (12,0)

Skyline: [[2,10],[3,15],[7,12],[12,0]]
```

### Template

```java
public List<List<Integer>> getSkyline(int[][] buildings) {
    List<int[]> events = new ArrayList<>();
    for (int[] b : buildings) {
        events.add(new int[]{b[0], -b[2]}); // start: negative height
        events.add(new int[]{b[1], b[2]});  // end: positive height
    }
    // Sort by x; if tie, smaller value first (start before end, taller start first)
    events.sort((a, b) -> a[0] != b[0] ? a[0] - b[0] : a[1] - b[1]);

    // Max-heap of active heights
    TreeMap<Integer, Integer> heights = new TreeMap<>(Collections.reverseOrder());
    heights.put(0, 1); // ground level
    int prevMax = 0;
    List<List<Integer>> result = new ArrayList<>();

    for (int[] e : events) {
        if (e[1] < 0) { // building start
            heights.merge(-e[1], 1, Integer::sum);
        } else { // building end
            int h = e[1];
            if (heights.get(h) == 1) heights.remove(h);
            else heights.merge(h, -1, Integer::sum);
        }
        int curMax = heights.firstKey();
        if (curMax != prevMax) {
            result.add(List.of(e[0], curMax));
            prevMax = curMax;
        }
    }
    return result;
}
```

### Why negative height trick?
Sorting by `(x, value)` where start heights are negative ensures:
- At same x, starts are processed before ends.
- Among starts at same x, taller buildings come first.
- Among ends at same x, shorter buildings are removed first.

### Complexity
- Time: O(n log n)
- Space: O(n)

---

## Pattern 3: Merge Intervals

**Problem**: Given intervals, merge all overlapping intervals.

### Signal
- "Merge overlapping", "combine ranges"

### Visualization

```
Input:  [1,3] [2,6] [8,10] [15,18]

Sorted: [1,3] [2,6] [8,10] [15,18]

Sweep:
  current = [1,3]
  [2,6]: 2 <= 3 → extend to [1,6]
  [8,10]: 8 > 6 → close [1,6], start [8,10]
  [15,18]: 15 > 10 → close [8,10], start [15,18]
  end → close [15,18]

Output: [1,6] [8,10] [15,18]
```

### Template

```java
public int[][] merge(int[][] intervals) {
    Arrays.sort(intervals, (a, b) -> a[0] - b[0]);
    List<int[]> merged = new ArrayList<>();
    int[] current = intervals[0];
    merged.add(current);

    for (int i = 1; i < intervals.length; i++) {
        if (intervals[i][0] <= current[1]) {
            current[1] = Math.max(current[1], intervals[i][1]); // extend
        } else {
            current = intervals[i]; // start new
            merged.add(current);
        }
    }
    return merged.toArray(new int[0][]);
}
```

### Complexity
- Time: O(n log n)
- Space: O(n) for output

---

## Pattern 4: Insert Interval

**Problem**: Insert a new interval into a sorted non-overlapping list, merging if necessary.

### Signal
- Sorted intervals + insert + merge overlaps

### Visualization

```
Existing: [1,2] [3,5] [6,7] [8,10] [12,16]
Insert:   [4,8]

Phase 1 - Before overlap (end < newStart):
  [1,2] → 2 < 4 → add directly

Phase 2 - Overlap (start <= newEnd):
  [3,5] → 3 <= 8 → merge: new = [min(4,3), max(8,5)] = [3,8]
  [6,7] → 6 <= 8 → merge: new = [3, max(8,7)] = [3,8]
  [8,10] → 8 <= 8 → merge: new = [3, max(8,10)] = [3,10]

Phase 3 - After overlap:
  [12,16] → 12 > 10 → add directly

Output: [1,2] [3,10] [12,16]
```

### Template

```java
public int[][] insert(int[][] intervals, int[] newInterval) {
    List<int[]> result = new ArrayList<>();
    int i = 0, n = intervals.length;

    // Phase 1: intervals completely before newInterval
    while (i < n && intervals[i][1] < newInterval[0]) {
        result.add(intervals[i++]);
    }

    // Phase 2: overlapping intervals — merge
    while (i < n && intervals[i][0] <= newInterval[1]) {
        newInterval[0] = Math.min(newInterval[0], intervals[i][0]);
        newInterval[1] = Math.max(newInterval[1], intervals[i][1]);
        i++;
    }
    result.add(newInterval);

    // Phase 3: intervals completely after
    while (i < n) {
        result.add(intervals[i++]);
    }
    return result.toArray(new int[0][]);
}
```

### Complexity
- Time: O(n)
- Space: O(n)

---

## Pattern 5: Interval List Intersections

**Problem**: Given two sorted lists of disjoint intervals, return their intersections.

### Signal
- Two sorted interval lists, find overlaps, two-pointer.

### Visualization

```
A: [0,2] [5,10] [13,23] [24,25]
B: [1,5] [8,12] [15,24] [25,26]

Two pointers i=0, j=0:

  A[0]=[0,2], B[0]=[1,5]:
    lo=max(0,1)=1, hi=min(2,5)=2 → lo<=hi → intersection [1,2]
    A ends first (2<5) → i++

  A[1]=[5,10], B[0]=[1,5]:
    lo=max(5,1)=5, hi=min(10,5)=5 → [5,5]
    B ends first (5<10) → j++

  A[1]=[5,10], B[1]=[8,12]:
    lo=max(5,8)=8, hi=min(10,12)=10 → [8,10]
    A ends first → i++

  ... continues ...

Output: [1,2],[5,5],[8,10],[15,23],[24,24],[25,25]
```

### Template

```java
public int[][] intervalIntersection(int[][] A, int[][] B) {
    List<int[]> result = new ArrayList<>();
    int i = 0, j = 0;

    while (i < A.length && j < B.length) {
        int lo = Math.max(A[i][0], B[j][0]);
        int hi = Math.min(A[i][1], B[j][1]);

        if (lo <= hi) {
            result.add(new int[]{lo, hi});
        }

        // Advance the pointer with the smaller endpoint
        if (A[i][1] < B[j][1]) i++;
        else j++;
    }
    return result.toArray(new int[0][]);
}
```

### Complexity
- Time: O(m + n)
- Space: O(m + n) for output

---

## Pattern 6: Rectangle Area / Overlap

**Problem**: Find total area covered by rectangles (handling overlaps).

### Signal
- 2D geometry, overlapping rectangles, "total area", coordinate compression.

### Visualization (Two Rectangles)

```
For simple 2-rectangle overlap (LC 223):

  ┌─────────┐
  │    A    ┌┼────────┐
  │         ││overlap │
  └─────────┼┘   B    │
             └─────────┘

Area = Area(A) + Area(B) - Area(overlap)
Overlap: [max(x1,x3), max(y1,y3)] to [min(x2,x4), min(y2,y4)]
```

### Template (Two Rectangles - LC 223)

```java
public int computeArea(int ax1, int ay1, int ax2, int ay2,
                       int bx1, int by1, int bx2, int by2) {
    int area1 = (ax2 - ax1) * (ay2 - ay1);
    int area2 = (bx2 - bx1) * (by2 - by1);

    // Overlap dimensions
    int overlapX = Math.max(0, Math.min(ax2, bx2) - Math.max(ax1, bx1));
    int overlapY = Math.max(0, Math.min(ay2, by2) - Math.max(ay1, by1));

    return area1 + area2 - overlapX * overlapY;
}
```

### Template (N Rectangles - Coordinate Compression + Sweep)

```java
public long rectangleArea(int[][] rectangles) {
    // Collect all unique x-coordinates
    TreeSet<Integer> xSet = new TreeSet<>();
    for (int[] r : rectangles) { xSet.add(r[0]); xSet.add(r[2]); }
    Integer[] xs = xSet.toArray(new Integer[0]);

    // Sweep vertically for each x-strip
    long MOD = 1_000_000_007, area = 0;
    for (int i = 0; i < xs.length - 1; i++) {
        int x1 = xs[i], x2 = xs[i + 1];
        // Collect y-intervals active in this x-strip
        List<int[]> yIntervals = new ArrayList<>();
        for (int[] r : rectangles) {
            if (r[0] <= x1 && x2 <= r[2]) {
                yIntervals.add(new int[]{r[1], r[3]});
            }
        }
        // Merge y-intervals to get covered height
        yIntervals.sort((a, b) -> a[0] - b[0]);
        long coveredY = 0;
        int curLo = -1, curHi = -1;
        for (int[] yi : yIntervals) {
            if (yi[0] > curHi) {
                coveredY += curHi - curLo;
                curLo = yi[0]; curHi = yi[1];
            } else {
                curHi = Math.max(curHi, yi[1]);
            }
        }
        coveredY += curHi - curLo;
        area = (area + (long)(x2 - x1) * coveredY) % MOD;
    }
    return (int) area;
}
```

### Complexity
- Two rectangles: O(1) time, O(1) space
- N rectangles (coord compression): O(n^2 log n) time, O(n) space

---

## Pattern 7: My Calendar I / II / III (TreeMap Event Sweep)

**Problem**:
- **Calendar I**: No double booking allowed.
- **Calendar II**: No triple booking allowed.
- **Calendar III**: Return max concurrent bookings after each insert.

### Signal
- Online interval insertion, need overlap count, TreeMap sweep.

### Visualization (Calendar III)

```
book(10,20) → map: {10:+1, 20:-1}
  sweep: 0→1→0  max=1

book(50,60) → map: {10:+1, 20:-1, 50:+1, 60:-1}
  sweep: 0→1→0→1→0  max=1

book(10,40) → map: {10:+2, 20:-1, 40:-1, 50:+1, 60:-1}
  sweep: 0→2→1→0→1→0  max=2

book(5,15) → map: {5:+1, 10:+2, 15:-1, 20:-1, 40:-1, 50:+1, 60:-1}
  sweep: 0→1→3→2→1→0→1→0  max=3
```

### Template (My Calendar III)

```java
class MyCalendarThree {
    private TreeMap<Integer, Integer> map;

    public MyCalendarThree() {
        map = new TreeMap<>();
    }

    public int book(int start, int end) {
        map.merge(start, 1, Integer::sum);
        map.merge(end, -1, Integer::sum);

        int active = 0, max = 0;
        for (int v : map.values()) {
            active += v;
            max = Math.max(max, active);
        }
        return max;
    }
}
```

### Template (My Calendar I - No Double Booking)

```java
class MyCalendar {
    private TreeMap<Integer, Integer> calendar; // start → end

    public MyCalendar() {
        calendar = new TreeMap<>();
    }

    public boolean book(int start, int end) {
        Integer prev = calendar.floorKey(start);
        Integer next = calendar.ceilingKey(start);

        if ((prev == null || calendar.get(prev) <= start) &&
            (next == null || end <= next)) {
            calendar.put(start, end);
            return true;
        }
        return false;
    }
}
```

### Template (My Calendar II - No Triple Booking)

```java
class MyCalendarTwo {
    private TreeMap<Integer, Integer> map;

    public MyCalendarTwo() {
        map = new TreeMap<>();
    }

    public boolean book(int start, int end) {
        map.merge(start, 1, Integer::sum);
        map.merge(end, -1, Integer::sum);

        int active = 0;
        for (int v : map.values()) {
            active += v;
            if (active >= 3) {
                // Rollback
                map.merge(start, -1, Integer::sum);
                map.merge(end, 1, Integer::sum);
                if (map.get(start) == 0) map.remove(start);
                if (map.get(end) == 0) map.remove(end);
                return false;
            }
        }
        return true;
    }
}
```

### Complexity
- Calendar I: O(log n) per book (TreeMap floorKey/ceilingKey)
- Calendar II: O(n) per book (sweep to check)
- Calendar III: O(n) per book (full sweep)

---

## Pattern 8: Car Pooling

**Problem**: Given trips `[numPassengers, from, to]` and vehicle capacity, determine if all trips can be completed.

### Signal
- Capacity constraint over a range, bounded coordinates (0-1000).

### Visualization

```
trips = [[2,1,5],[3,3,7]], capacity = 4

Difference array (range 0..1000):
  trip [2,1,5]: diff[1] += 2, diff[5] -= 2
  trip [3,3,7]: diff[3] += 3, diff[7] -= 3

Prefix sum:
  pos: 0  1  2  3  4  5  6  7
  pax: 0  2  2  5  5  3  3  0
                   ▲
                   5 > 4 = IMPOSSIBLE

Answer: false
```

### Template

```java
public boolean carPooling(int[][] trips, int capacity) {
    int[] diff = new int[1001];
    for (int[] trip : trips) {
        diff[trip[1]] += trip[0];
        diff[trip[2]] -= trip[0];
    }
    int passengers = 0;
    for (int d : diff) {
        passengers += d;
        if (passengers > capacity) return false;
    }
    return true;
}
```

### Complexity
- Time: O(n + 1001) = O(n)
- Space: O(1001) = O(1)

---

## Pattern 9: Points That Intersect With Cars

**Problem**: Given cars as intervals on a number line, count how many integer points are covered by at least one car.

### Signal
- Count covered integer points across intervals → difference array or merge intervals.

### Visualization

```
cars = [[3,6],[1,5],[4,7]]

Merge approach:
  sorted: [1,5],[3,6],[4,7]
  merge:  [1,7]
  points: 7 - 1 + 1 = 7

Difference array approach (if range is small):
  diff[1]++, diff[6]--    (for [1,5] inclusive → diff[5+1]--)
  diff[3]++, diff[7]--
  diff[4]++, diff[8]--

  prefix sum → count positions where sum > 0
```

### Template (Merge Intervals Approach)

```java
public int numberOfPoints(List<List<Integer>> nums) {
    nums.sort((a, b) -> a.get(0) - b.get(0));
    int count = 0;
    int start = nums.get(0).get(0), end = nums.get(0).get(1);

    for (int i = 1; i < nums.size(); i++) {
        if (nums.get(i).get(0) <= end) {
            end = Math.max(end, nums.get(i).get(1));
        } else {
            count += end - start + 1;
            start = nums.get(i).get(0);
            end = nums.get(i).get(1);
        }
    }
    count += end - start + 1;
    return count;
}
```

### Template (Difference Array)

```java
public int numberOfPoints(List<List<Integer>> nums) {
    int[] diff = new int[102]; // constraints: 1 <= start <= end <= 100
    for (List<Integer> car : nums) {
        diff[car.get(0)]++;
        diff[car.get(1) + 1]--;
    }
    int count = 0, active = 0;
    for (int i = 0; i < diff.length; i++) {
        active += diff[i];
        if (active > 0) count++;
    }
    return count;
}
```

### Complexity
- Merge approach: O(n log n) time, O(1) extra space
- Difference array: O(n + R) time, O(R) space

---

## Pattern 10: Count Asteroids Destroyed (Processing Events in Order)

**Problem**: Given planet mass and asteroid masses, planet absorbs asteroids in order (smallest first). If planet mass >= asteroid, absorb (mass += asteroid). Return if all can be destroyed.

### Signal
- Process events in sorted order, accumulate state, check feasibility.

### Visualization

```
mass = 10, asteroids = [3,9,19,5,21]

Sort: [3, 5, 9, 19, 21]

Sweep through sorted events:
  mass=10 >= 3  → absorb → mass=13
  mass=13 >= 5  → absorb → mass=18
  mass=18 >= 9  → absorb → mass=27
  mass=27 >= 19 → absorb → mass=46
  mass=46 >= 21 → absorb → mass=67

All destroyed → true
```

### Template

```java
public boolean asteroidsDestroyed(int mass, int[] asteroids) {
    Arrays.sort(asteroids);
    long m = mass;
    for (int asteroid : asteroids) {
        if (m < asteroid) return false;
        m += asteroid;
    }
    return true;
}
```

### Complexity
- Time: O(n log n)
- Space: O(1) (in-place sort)

---

## Master Sweep Line Animation

```
Problem: Find max overlapping intervals
Input: [1,4], [2,6], [4,7], [5,8]

Step-by-step sweep:

Events sorted: (1,+1) (2,+1) (4,+1) (4,-1) (5,+1) (6,-1) (7,-1) (8,-1)

t=1: ─────┬──────────────────────────────
     +1   │ active = 1
           │
t=2: ─────┼──┬───────────────────────────
     +1   │  │ active = 2
           │  │
t=4: ─────┼──┼──┬────────────────────────
     +1   │  │  │ active = 3  ← MAX
           │  │  │
t=4: ─────┼──┼──┼────────────────────────
     -1   │  │     active = 2  (first interval ends)
           │  │
t=5: ─────┼──┼─────┬─────────────────────
     +1   │  │     │ active = 3  ← MAX
           │  │     │
t=6: ─────┼──┼─────┼─────────────────────
     -1      │     │ active = 2
              │     │
t=7: ────────┼─────┼─────────────────────
     -1            │ active = 1
                    │
t=8: ──────────────┼─────────────────────
     -1              active = 0

Answer: max = 3
```

---

## Variant Summary Table

| # | Problem | Core Technique | Key Insight |
|---|---------|---------------|-------------|
| 1 | Meeting Rooms II | Event sort + counter | Separate start/end arrays, two-pointer |
| 2 | Skyline | Events + max-heap (TreeMap) | Track max active height, emit on change |
| 3 | Merge Intervals | Sort + greedy extend | Compare next.start vs current.end |
| 4 | Insert Interval | Three-phase scan | Before / overlap / after |
| 5 | Interval Intersections | Two-pointer | lo=max(starts), hi=min(ends), advance smaller end |
| 6 | Rectangle Area | Coord compression + sweep | 2D → series of 1D merge problems |
| 7 | My Calendar I/II/III | TreeMap event map | Insert +1/-1, sweep values, check constraint |
| 8 | Car Pooling | Difference array | Bounded coords → O(R) array |
| 9 | Points With Cars | Diff array or merge | Count covered integer positions |
| 10 | Asteroids Destroyed | Sort + accumulate | Greedy: smallest first maximizes mass |

---

## Edge Cases Checklist

- [ ] Empty input
- [ ] Single interval
- [ ] Intervals that touch at endpoints: `[1,5],[5,8]` — overlapping or not? (problem-specific)
- [ ] Intervals already sorted
- [ ] Intervals with same start time
- [ ] Intervals fully contained within another
- [ ] Integer overflow when accumulating (use `long`)
- [ ] Tie-breaking in event sort (start before end at same point? depends on problem)

---

## Tie-Breaking Rules

| Problem Type | At Same Coordinate |
|---|---|
| Max overlap count (inclusive ends) | Process +1 before -1 |
| Max overlap count (exclusive ends) | Process -1 before +1 |
| Skyline | Process starts before ends; taller starts first; shorter ends first |
| General | Define based on whether endpoints are inclusive or exclusive |

```java
// Inclusive intervals: at same point, start before end
Arrays.sort(events, (a, b) -> a[0] != b[0] ? a[0] - b[0] : a[1] - b[1]);
// where start = +1 (positive), end = -1 (negative)
// Wait — this puts -1 first! For inclusive, we want +1 first:
Arrays.sort(events, (a, b) -> a[0] != b[0] ? a[0] - b[0] : b[1] - a[1]);
```

Always verify tie-breaking with a test case where intervals share an endpoint.
