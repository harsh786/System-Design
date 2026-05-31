# 16 - Greedy Algorithms

## When Greedy Works vs When DP Is Needed

| Greedy Works | DP Required |
|---|---|
| Optimal substructure + greedy choice property | Optimal substructure but no greedy choice property |
| Locally optimal => globally optimal | Local optimum can lead to global suboptimum |
| Choices are irrevocable and safe | Need to explore multiple branches |
| Problem has matroid structure | Overlapping subproblems with dependencies |

**Key Differentiator**: After making a greedy choice, does the remaining problem reduce to a *single* smaller subproblem of the same form? If yes → Greedy. If you need results from *multiple* subproblems → DP.

**Examples**:
- Fractional Knapsack → Greedy (take best ratio greedily, remainder is same problem)
- 0/1 Knapsack → DP (taking/not-taking creates two branches that interact)
- Interval Scheduling (max non-overlapping) → Greedy
- Weighted Interval Scheduling → DP (weights break the exchange argument)

---

## Exchange Argument (Proof Technique)

The standard method to prove greedy correctness:

1. Let `G` = greedy solution, `O` = any optimal solution
2. Find the first point where `G` and `O` differ
3. Show you can **exchange** `O`'s choice for `G`'s choice without worsening `O`
4. By induction, transform `O` into `G` → `G` is optimal

**Greedy-Stays-Ahead** (alternative): Show that at every step, greedy's partial solution is at least as good as any other algorithm's partial solution at that step.

---

## Decision Flowchart

```
Is there an obvious "locally best" choice?
│
├─ YES → Can you prove exchange argument?
│         │
│         ├─ YES → Greedy works
│         └─ NO  → Try DP / verify with counterexample
│
└─ NO → Does problem have overlapping subproblems?
          │
          ├─ YES → DP
          └─ NO  → Divide & Conquer or Brute Force
```

---

## Pattern 1: Interval Scheduling - Maximum Non-Overlapping

### Signal
- Given intervals, select maximum number of non-overlapping ones
- LC 435 (inverse: min removals), LC 452

### Template (Java)

```java
public int maxNonOverlapping(int[][] intervals) {
    // Sort by END time — the greedy choice
    Arrays.sort(intervals, (a, b) -> Integer.compare(a[1], b[1]));
    
    int count = 0;
    int prevEnd = Integer.MIN_VALUE;
    
    for (int[] interval : intervals) {
        if (interval[0] >= prevEnd) {  // no overlap (use > for strict)
            count++;
            prevEnd = interval[1];
        }
    }
    return count;
}
```

### Proof Sketch (Greedy-Stays-Ahead)

Let `g1, g2, ..., gk` be greedy's selections (sorted by end), `o1, o2, ..., om` be OPT's.
- **Claim**: `g_i.end <= o_i.end` for all `i` (greedy finishes no later at each step).
- **Base**: `g1` has earliest end of all → `g1.end <= o1.end`.
- **Inductive step**: Assume `g_i.end <= o_i.end`. Then `o_{i+1}.start >= o_i.end >= g_i.end`, so `o_{i+1}` is a candidate for greedy at step `i+1`. Greedy picks earliest end among candidates → `g_{i+1}.end <= o_{i+1}.end`.
- Since greedy stays ahead, it selects at least as many as OPT → `k >= m`.

### Variants
- Sort by **start** → WRONG (long interval blocks many short ones)
- Sort by **length** → WRONG (short interval can bridge two groups)
- **Weighted** version → DP required

### Complexity
- Time: O(n log n) sort + O(n) scan
- Space: O(1) extra (or O(n) for sort)

---

## Pattern 2: Interval Partitioning - Minimum Resources

### Signal
- Schedule all intervals using minimum number of rooms/resources
- LC 253 (Meeting Rooms II)

### Template (Java)

```java
public int minMeetingRooms(int[][] intervals) {
    // Sort by START time
    Arrays.sort(intervals, (a, b) -> Integer.compare(a[0], b[0]));
    
    // Min-heap tracks end times of active rooms
    PriorityQueue<Integer> heap = new PriorityQueue<>();
    
    for (int[] interval : intervals) {
        // If earliest-ending room is free, reuse it
        if (!heap.isEmpty() && heap.peek() <= interval[0]) {
            heap.poll();
        }
        heap.offer(interval[1]);
    }
    return heap.size();
}
```

**Alternative — Sweep Line**:
```java
public int minMeetingRooms(int[][] intervals) {
    int[] starts = new int[intervals.length];
    int[] ends = new int[intervals.length];
    for (int i = 0; i < intervals.length; i++) {
        starts[i] = intervals[i][0];
        ends[i] = intervals[i][1];
    }
    Arrays.sort(starts);
    Arrays.sort(ends);
    
    int rooms = 0, endPtr = 0;
    for (int start : starts) {
        if (start < ends[endPtr]) rooms++;
        else endPtr++;
    }
    return rooms;
}
```

### Proof Sketch (Exchange Argument)

At step where greedy opens room `k`, there are `k` intervals all overlapping at that point (the current interval overlaps with the `k-1` intervals in the heap). Any algorithm needs at least `k` resources for this set of mutually overlapping intervals. Therefore greedy's answer = maximum overlap depth = lower bound = optimal.

### Variants
- Return actual assignment → track room IDs in heap
- Weighted variant (CPU scheduling) → different approach needed

### Complexity
- Time: O(n log n)
- Space: O(n) for the heap

---

## Pattern 3: Jump Game I & II

### Signal
- Array of jump lengths, can you reach end / min jumps to reach end
- LC 55, LC 45

### Template (Java) — Jump Game I

```java
public boolean canJump(int[] nums) {
    int farthest = 0;
    for (int i = 0; i <= farthest && i < nums.length; i++) {
        farthest = Math.max(farthest, i + nums[i]);
        if (farthest >= nums.length - 1) return true;
    }
    return false;
}
```

### Template (Java) — Jump Game II (BFS-like layers)

```java
public int jump(int[] nums) {
    int jumps = 0, curEnd = 0, farthest = 0;
    
    for (int i = 0; i < nums.length - 1; i++) {
        farthest = Math.max(farthest, i + nums[i]);
        if (i == curEnd) {        // exhausted current layer
            jumps++;
            curEnd = farthest;
            if (curEnd >= nums.length - 1) break;
        }
    }
    return jumps;
}
```

### Proof Sketch (Greedy-Stays-Ahead)

For Jump II: Each "layer" represents positions reachable in exactly `k` jumps. Greedy expands each layer to its maximum extent. Any solution that reaches the end in fewer jumps would need a layer that extends further than ours — impossible since we already took the maximum reach at each step.

### Variants
- Jump Game III (BFS, not greedy — bidirectional jumps)
- Jump Game IV (BFS on value-based graph)
- Minimum jumps with cost → DP

### Complexity
- Time: O(n) single pass
- Space: O(1)

---

## Pattern 4: Gas Station

### Signal
- Circular route, gas[i] and cost[i], find starting station for full circuit
- LC 134

### Template (Java)

```java
public int canCompleteCircuit(int[] gas, int[] cost) {
    int totalSurplus = 0;
    int currentSurplus = 0;
    int start = 0;
    
    for (int i = 0; i < gas.length; i++) {
        int diff = gas[i] - cost[i];
        totalSurplus += diff;
        currentSurplus += diff;
        
        if (currentSurplus < 0) {
            // Can't start from 'start' or anywhere before i
            start = i + 1;
            currentSurplus = 0;
        }
    }
    return totalSurplus >= 0 ? start : -1;
}
```

### Proof Sketch (Exchange Argument)

1. If `totalSurplus < 0`, no solution exists (not enough gas globally).
2. If `totalSurplus >= 0`, a solution exists. Why is `start` correct?
   - Any station before `start` (in the last reset window) fails because prefix sum went negative.
   - Starting at `start`: surplus from `start` to end = `totalSurplus - (sum from 0 to start-1)`. Since total >= 0 and the prefix 0..start-1 is the deficit portion, the suffix has enough surplus to cover the wrap-around deficit.

### Variants
- Multiple valid starts → problem guarantees unique answer
- Minimize total fuel purchased → different problem structure

### Complexity
- Time: O(n)
- Space: O(1)

---

## Pattern 5: Task Scheduler

### Signal
- Tasks with cooldown, minimize total time (including idles)
- LC 621

### Template (Java) — Formula Approach

```java
public int leastInterval(char[] tasks, int n) {
    int[] freq = new int[26];
    for (char t : tasks) freq[t - 'A']++;
    
    int maxFreq = Arrays.stream(freq).max().getAsInt();
    int maxCount = (int) Arrays.stream(freq).filter(f -> f == maxFreq).count();
    
    // (maxFreq-1) full "frames" of size (n+1), plus final partial frame
    int formulaResult = (maxFreq - 1) * (n + 1) + maxCount;
    
    // Answer is max of formula and total tasks (when no idle needed)
    return Math.max(formulaResult, tasks.length);
}
```

### Template (Java) — Heap Approach (for actual ordering)

```java
public int leastInterval(char[] tasks, int n) {
    int[] freq = new int[26];
    for (char t : tasks) freq[t - 'A']++;
    
    PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Collections.reverseOrder());
    for (int f : freq) if (f > 0) maxHeap.offer(f);
    
    int time = 0;
    Queue<int[]> cooldown = new LinkedList<>(); // [remaining_count, available_time]
    
    while (!maxHeap.isEmpty() || !cooldown.isEmpty()) {
        time++;
        if (!maxHeap.isEmpty()) {
            int cnt = maxHeap.poll() - 1;
            if (cnt > 0) cooldown.offer(new int[]{cnt, time + n});
        }
        if (!cooldown.isEmpty() && cooldown.peek()[1] == time) {
            maxHeap.offer(cooldown.poll()[0]);
        }
    }
    return time;
}
```

### Proof Sketch

The most frequent task(s) create a mandatory frame structure. Between consecutive executions of the max-frequency task, we must fill `n` slots. The formula computes the minimum skeleton; if total tasks overflow the skeleton, no idle is needed.

### Variants
- With specific ordering constraints → topological sort + greedy
- Task Scheduler II (LC 2365) — different cooldown per task type

### Complexity
- Formula: O(n) time, O(1) space (26 chars)
- Heap: O(n * 26 log 26) ≈ O(n) time, O(26) space

---

## Pattern 6: Partition Labels

### Signal
- Partition string so each character appears in at most one part, maximize partitions
- LC 763

### Template (Java)

```java
public List<Integer> partitionLabels(String s) {
    int[] lastOccurrence = new int[26];
    for (int i = 0; i < s.length(); i++) {
        lastOccurrence[s.charAt(i) - 'a'] = i;
    }
    
    List<Integer> result = new ArrayList<>();
    int start = 0, end = 0;
    
    for (int i = 0; i < s.length(); i++) {
        end = Math.max(end, lastOccurrence[s.charAt(i) - 'a']);
        if (i == end) {
            result.add(end - start + 1);
            start = i + 1;
        }
    }
    return result;
}
```

### Proof Sketch (Exchange Argument)

At each position, we *must* extend the current partition to at least `lastOccurrence[char]`. Cutting earlier would split a character across partitions. Cutting at exactly `end` when `i == end` is the earliest safe cut → maximizes number of partitions.

### Variants
- Return partition indices instead of sizes
- Merge Intervals variant (same structure, different framing)

### Complexity
- Time: O(n)
- Space: O(1) (26-element array)

---

## Pattern 7: Candy Distribution

### Signal
- Children in line with ratings, each gets >= 1 candy, higher rating than neighbor → more candy
- LC 135

### Template (Java)

```java
public int candy(int[] ratings) {
    int n = ratings.length;
    int[] candies = new int[n];
    Arrays.fill(candies, 1);
    
    // Left pass: satisfy left neighbor constraint
    for (int i = 1; i < n; i++) {
        if (ratings[i] > ratings[i - 1]) {
            candies[i] = candies[i - 1] + 1;
        }
    }
    
    // Right pass: satisfy right neighbor constraint
    for (int i = n - 2; i >= 0; i--) {
        if (ratings[i] > ratings[i + 1]) {
            candies[i] = Math.max(candies[i], candies[i + 1] + 1);
        }
    }
    
    int total = 0;
    for (int c : candies) total += c;
    return total;
}
```

### Proof Sketch

- After left pass: all left-neighbor constraints satisfied with minimum possible values.
- After right pass (using `max`): right-neighbor constraints satisfied without violating left constraints.
- Each child has the minimum candy satisfying both directions → optimal.

### Variants
- O(1) space solution using slope counting (up/down sequences)
- Circular arrangement → more complex

### Complexity
- Time: O(n)
- Space: O(n) for candies array

---

## Pattern 8: Assign Cookies

### Signal
- Greed factors and cookie sizes, maximize satisfied children
- LC 455

### Template (Java)

```java
public int findContentChildren(int[] children, int[] cookies) {
    Arrays.sort(children);
    Arrays.sort(cookies);
    
    int child = 0, cookie = 0;
    while (child < children.length && cookie < cookies.length) {
        if (cookies[cookie] >= children[child]) {
            child++;  // child satisfied
        }
        cookie++;     // cookie used or too small, move on
    }
    return child;
}
```

### Proof Sketch (Exchange Argument)

Sort both. Assign smallest sufficient cookie to least greedy child. If OPT assigns a larger cookie `c'` to this child, we can swap `c'` with our smaller cookie — the other child either still gets enough or gets more. No child is worse off → greedy is optimal.

### Variants
- Each cookie can be split → fractional assignment
- Multiple cookies per child → knapsack territory

### Complexity
- Time: O(n log n + m log m)
- Space: O(1) extra

---

## Pattern 9: Non-Overlapping Intervals / Minimum Removals

### Signal
- Minimum intervals to remove so rest are non-overlapping
- LC 435

### Template (Java)

```java
public int eraseOverlapIntervals(int[][] intervals) {
    // Same as max non-overlapping, then subtract
    Arrays.sort(intervals, (a, b) -> Integer.compare(a[1], b[1]));
    
    int kept = 0;
    int prevEnd = Integer.MIN_VALUE;
    
    for (int[] interval : intervals) {
        if (interval[0] >= prevEnd) {
            kept++;
            prevEnd = interval[1];
        }
    }
    return intervals.length - kept;
}
```

### Proof Sketch

This is the **complement** of Pattern 1. Maximizing non-overlapping intervals = minimizing removals. Same greedy-stays-ahead proof applies.

### Complexity
- Time: O(n log n)
- Space: O(1)

---

## Pattern 10: Queue Reconstruction by Height

### Signal
- People described by (height, # people taller in front), reconstruct queue
- LC 406

### Template (Java)

```java
public int[][] reconstructQueue(int[][] people) {
    // Sort: tallest first; same height → fewer people in front first
    Arrays.sort(people, (a, b) -> 
        a[0] != b[0] ? b[0] - a[0] : a[1] - b[1]);
    
    List<int[]> result = new ArrayList<>();
    for (int[] person : people) {
        // Insert at index = k value
        result.add(person[1], person);
    }
    return result.toArray(new int[0][]);
}
```

### Proof Sketch

Process tallest first. When inserting person `(h, k)`, all already-placed people are >= h, so position `k` correctly counts taller-or-equal people in front. Shorter people inserted later don't affect taller people's counts (they're invisible to them).

### Variants
- If heights are unique → simpler reasoning
- With constraints on adjacent positions → different approach

### Complexity
- Time: O(n^2) due to list insertions (O(n log n) sort + O(n^2) inserts)
- Space: O(n)

---

## Pattern 11: Minimum Arrows to Burst Balloons

### Signal
- Balloons as intervals on x-axis, vertical arrows, find minimum arrows
- LC 452

### Template (Java)

```java
public int findMinArrowShots(int[][] points) {
    // Sort by END coordinate
    Arrays.sort(points, (a, b) -> Integer.compare(a[1], b[1]));
    
    int arrows = 1;
    int arrowPos = points[0][1];
    
    for (int i = 1; i < points.length; i++) {
        // If balloon starts after current arrow position, need new arrow
        if (points[i][0] > arrowPos) {
            arrows++;
            arrowPos = points[i][1];
        }
    }
    return arrows;
}
```

### Proof Sketch

Identical structure to interval scheduling. Each arrow "covers" a maximal set of overlapping balloons. Shooting at the earliest-ending balloon's end point greedily covers the most subsequent balloons. Same greedy-stays-ahead argument as Pattern 1.

### Variants
- Balloons in 2D → NP-hard (geometric set cover)
- Points touching edges count as burst (use `>=`) vs strict (`>`)

### Complexity
- Time: O(n log n)
- Space: O(1)

---

## Pattern 12: Fractional Knapsack

### Signal
- Items with weight and value, can take fractions, maximize value within capacity
- Classic greedy (contrast with 0/1 knapsack which needs DP)

### Template (Java)

```java
public double fractionalKnapsack(int capacity, int[][] items) {
    // items[i] = {value, weight}
    // Sort by value/weight ratio descending
    Arrays.sort(items, (a, b) -> 
        Double.compare((double) b[0] / b[1], (double) a[0] / a[1]));
    
    double totalValue = 0;
    int remaining = capacity;
    
    for (int[] item : items) {
        if (remaining == 0) break;
        
        if (item[1] <= remaining) {
            // Take whole item
            totalValue += item[0];
            remaining -= item[1];
        } else {
            // Take fraction
            totalValue += (double) item[0] * remaining / item[1];
            remaining = 0;
        }
    }
    return totalValue;
}
```

### Proof Sketch (Exchange Argument)

Suppose OPT takes less of item `i` (best ratio) and more of item `j` (worse ratio). Exchange: replace amount `x` of item `j` with same weight of item `i`. Value change = `x * (ratio_i - ratio_j) > 0`. Contradiction with OPT being optimal. Therefore, greedy (take best ratio first) is optimal.

### Variants
- 0/1 Knapsack → DP (can't take fractions, exchange argument breaks)
- Bounded Knapsack → DP
- Multiple knapsacks → more complex

### Complexity
- Time: O(n log n)
- Space: O(1)

---

## Summary Table

| # | Pattern | Sort Key | Core Insight | Time |
|---|---------|----------|--------------|------|
| 1 | Max Non-Overlapping | End time | Earliest finish leaves most room | O(n log n) |
| 2 | Min Resources | Start time + heap | Reuse earliest-freed resource | O(n log n) |
| 3 | Jump Game | — | Track farthest reachable per layer | O(n) |
| 4 | Gas Station | — | Reset start on deficit | O(n) |
| 5 | Task Scheduler | Frequency | Frame structure from max-freq task | O(n) |
| 6 | Partition Labels | — | Extend to last occurrence | O(n) |
| 7 | Candy | — | Two-pass left/right | O(n) |
| 8 | Assign Cookies | Both arrays | Smallest sufficient match | O(n log n) |
| 9 | Min Removals | End time | Complement of max non-overlapping | O(n log n) |
| 10 | Queue Reconstruction | Height desc | Tall first, insert at k | O(n^2) |
| 11 | Min Arrows | End coordinate | Same as interval scheduling | O(n log n) |
| 12 | Fractional Knapsack | Value/weight | Best ratio first, fractions allowed | O(n log n) |

---

## Common Pitfalls

1. **Sorting by wrong key**: Start vs End matters enormously (Pattern 1 vs 2)
2. **Integer overflow in comparators**: Use `Integer.compare()` not subtraction
3. **Boundary conditions**: `>=` vs `>` for overlap (touching intervals)
4. **Assuming greedy without proof**: Always verify with exchange argument or counterexample
5. **Applying greedy to weighted variants**: Weights almost always require DP
