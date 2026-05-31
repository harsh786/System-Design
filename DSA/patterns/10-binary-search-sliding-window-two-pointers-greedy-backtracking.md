# Binary Search, Sliding Window, Two Pointers, Greedy, Backtracking - Pattern Guide

---

# BINARY SEARCH

## Core Insight
Binary search is NOT just "find element in sorted array." It's finding the **boundary where a predicate changes from FALSE to TRUE**.

```
Index:    0  1  2  3  4  5  6  7  8  9
Predicate: F  F  F  F  T  T  T  T  T  T
                      ^
                 First TRUE = answer
```

## Pattern BS.1: Classic Search
```java
int lo = 0, hi = n - 1;
while (lo <= hi) {
    int mid = lo + (hi - lo) / 2;
    if (nums[mid] == target) return mid;
    else if (nums[mid] < target) lo = mid + 1;
    else hi = mid - 1;
}
return -1;
```

## Pattern BS.2: First TRUE (Lower Bound / Leftmost)
```java
int lo = 0, hi = n;  // hi = n (not n-1) to handle "all false" case
while (lo < hi) {
    int mid = lo + (hi - lo) / 2;
    if (condition(mid)) hi = mid;      // mid might be answer
    else lo = mid + 1;                  // mid definitely not answer
}
return lo;  // first position where condition is true
```

## Pattern BS.3: Last TRUE (Upper Bound / Rightmost)
```java
int lo = 0, hi = n - 1;
while (lo < hi) {
    int mid = lo + (hi - lo + 1) / 2;  // CEIL to avoid infinite loop
    if (condition(mid)) lo = mid;       // mid might be answer
    else hi = mid - 1;
}
return lo;
```

## Pattern BS.4: Binary Search on Answer (Minimize/Maximize)

**Signal:** "Minimize the maximum", "find minimum speed/capacity such that..."

```java
int lo = minPossible, hi = maxPossible;
while (lo < hi) {
    int mid = lo + (hi - lo) / 2;
    if (feasible(mid)) hi = mid;    // can do it with mid → try smaller
    else lo = mid + 1;               // can't → need more
}
return lo;
```

### Examples
| Problem | lo | hi | feasible(mid) |
|---------|----|----|--------------|
| Koko Eating Bananas | 1 | max(piles) | Can finish in H hours at speed=mid? |
| Split Array Largest Sum | max(nums) | sum(nums) | Can split into ≤m parts with max≤mid? |
| Ship Packages in D Days | max(weights) | sum(weights) | Can ship in ≤D days with cap=mid? |
| Magnetic Force | 1 | maxDist | Can place all balls with min gap≥mid? |

## Pattern BS.5: Rotated Sorted Array
```java
int lo = 0, hi = n - 1;
while (lo <= hi) {
    int mid = (lo + hi) / 2;
    if (nums[mid] == target) return mid;
    
    if (nums[lo] <= nums[mid]) {        // left half sorted
        if (nums[lo] <= target && target < nums[mid]) hi = mid - 1;
        else lo = mid + 1;
    } else {                            // right half sorted
        if (nums[mid] < target && target <= nums[hi]) lo = mid + 1;
        else hi = mid - 1;
    }
}
```

---

# SLIDING WINDOW

## Decision Matrix
| Question | Pattern |
|----------|---------|
| Fixed size K? | Fixed Window |
| LONGEST valid? | Expand + shrink when INVALID |
| SHORTEST valid? | Expand + shrink while VALID |
| Contains all chars? | Frequency map + have/need |

## Pattern SW.1: Fixed Window
```java
// Build initial window
int windowSum = 0;
for (int i = 0; i < k; i++) windowSum += nums[i];
int maxSum = windowSum;

// Slide
for (int i = k; i < n; i++) {
    windowSum += nums[i] - nums[i - k];  // add new, remove old
    maxSum = Math.max(maxSum, windowSum);
}
```

## Pattern SW.2: Variable - Longest Valid
```java
int left = 0, maxLen = 0;
for (int right = 0; right < n; right++) {
    // EXPAND: add nums[right] to window state
    while (windowIsINVALID()) {
        // SHRINK: remove nums[left] from window
        left++;
    }
    maxLen = Math.max(maxLen, right - left + 1);
}
```

## Pattern SW.3: Variable - Shortest Valid
```java
int left = 0, minLen = Integer.MAX_VALUE;
for (int right = 0; right < n; right++) {
    // EXPAND
    while (windowIsVALID()) {
        minLen = Math.min(minLen, right - left + 1);
        // SHRINK
        left++;
    }
}
```

## Pattern SW.4: Frequency Map Window (Min Window Substring)
```java
Map<Character, Integer> need = count(pattern);
int have = 0, required = need.size();
Map<Character, Integer> window = new HashMap<>();
int left = 0, minLen = Integer.MAX_VALUE, minStart = 0;

for (int right = 0; right < n; right++) {
    char c = s.charAt(right);
    window.merge(c, 1, Integer::sum);
    if (window.get(c).equals(need.get(c))) have++;
    
    while (have == required) {
        if (right - left + 1 < minLen) {
            minLen = right - left + 1;
            minStart = left;
        }
        char d = s.charAt(left);
        window.merge(d, -1, Integer::sum);
        if (need.containsKey(d) && window.get(d) < need.get(d)) have--;
        left++;
    }
}
```

---

# TWO POINTERS

## Pattern TP.1: Opposite Ends (Sorted Array)
```java
int left = 0, right = n - 1;
while (left < right) {
    int sum = nums[left] + nums[right];
    if (sum == target) return result;
    else if (sum < target) left++;
    else right--;
}
```

## Pattern TP.2: 3Sum
```java
Arrays.sort(nums);
for (int i = 0; i < n - 2; i++) {
    if (i > 0 && nums[i] == nums[i-1]) continue;  // skip dups
    int lo = i + 1, hi = n - 1;
    while (lo < hi) {
        int sum = nums[i] + nums[lo] + nums[hi];
        if (sum == 0) {
            result.add(List.of(nums[i], nums[lo], nums[hi]));
            while (lo < hi && nums[lo] == nums[lo+1]) lo++;  // skip dups
            while (lo < hi && nums[hi] == nums[hi-1]) hi--;
            lo++; hi--;
        } else if (sum < 0) lo++;
        else hi--;
    }
}
```

## Pattern TP.3: Container With Most Water
```java
int left = 0, right = n - 1, maxArea = 0;
while (left < right) {
    int area = Math.min(height[left], height[right]) * (right - left);
    maxArea = Math.max(maxArea, area);
    if (height[left] < height[right]) left++;   // move shorter side
    else right--;
}
```

## Pattern TP.4: Trapping Rain Water
```java
int left = 0, right = n-1, leftMax = 0, rightMax = 0, water = 0;
while (left < right) {
    if (height[left] < height[right]) {
        leftMax = Math.max(leftMax, height[left]);
        water += leftMax - height[left];
        left++;
    } else {
        rightMax = Math.max(rightMax, height[right]);
        water += rightMax - height[right];
        right--;
    }
}
```

---

# GREEDY

## When Does Greedy Work?
- **Exchange argument:** Any swap of greedy choice with alternative doesn't improve result
- **Greedy stays ahead:** At every step, greedy solution ≥ any other solution

## Pattern G.1: Interval Scheduling (Sort by End)
```java
// Maximum non-overlapping intervals
Arrays.sort(intervals, (a,b) -> a[1] - b[1]);  // sort by END
int count = 0, lastEnd = Integer.MIN_VALUE;
for (int[] interval : intervals) {
    if (interval[0] >= lastEnd) {
        count++;
        lastEnd = interval[1];
    }
}
```

## Pattern G.2: Jump Game (Farthest Reach)
```java
// Can reach end?
int farthest = 0;
for (int i = 0; i < n; i++) {
    if (i > farthest) return false;
    farthest = Math.max(farthest, i + nums[i]);
}
return true;

// Min jumps to reach end
int jumps = 0, curEnd = 0, farthest = 0;
for (int i = 0; i < n - 1; i++) {
    farthest = Math.max(farthest, i + nums[i]);
    if (i == curEnd) { jumps++; curEnd = farthest; }
}
```

## Pattern G.3: Task Scheduler
```java
// Minimum intervals to complete all tasks with cooldown n
int maxFreq = max frequency;
int maxCount = number of tasks with maxFreq;
int result = Math.max(tasks.length, (maxFreq - 1) * (n + 1) + maxCount);
```

## Pattern G.4: Gas Station (Circular)
```java
int tank = 0, total = 0, start = 0;
for (int i = 0; i < n; i++) {
    int diff = gas[i] - cost[i];
    tank += diff;
    total += diff;
    if (tank < 0) { start = i + 1; tank = 0; }
}
return total >= 0 ? start : -1;
```

## Pattern G.5: Partition Labels
```java
int[] last = new int[26];
for (int i = 0; i < s.length(); i++) last[s.charAt(i)-'a'] = i;
int start = 0, end = 0;
for (int i = 0; i < s.length(); i++) {
    end = Math.max(end, last[s.charAt(i)-'a']);
    if (i == end) { result.add(end - start + 1); start = i + 1; }
}
```

---

# BACKTRACKING

## Template
```java
void backtrack(state, choices, result) {
    if (isGoal(state)) { result.add(copy(state)); return; }
    for (choice in validChoices) {
        make(choice);                    // CHOOSE
        backtrack(newState, ...);        // EXPLORE
        undo(choice);                    // UNCHOOSE (backtrack)
    }
}
```

## Pattern BT.1: Subsets (All 2^n)
```java
void backtrack(int start, List<Integer> current) {
    result.add(new ArrayList<>(current));  // every node is valid
    for (int i = start; i < n; i++) {
        current.add(nums[i]);
        backtrack(i + 1, current);         // i+1 = no reuse
        current.remove(current.size() - 1);
    }
}
```

## Pattern BT.2: Permutations
```java
void backtrack(List<Integer> current, boolean[] used) {
    if (current.size() == n) { result.add(new ArrayList<>(current)); return; }
    for (int i = 0; i < n; i++) {
        if (used[i]) continue;
        if (i > 0 && nums[i] == nums[i-1] && !used[i-1]) continue; // skip dups
        used[i] = true;
        current.add(nums[i]);
        backtrack(current, used);
        current.remove(current.size() - 1);
        used[i] = false;
    }
}
```

## Pattern BT.3: Combination Sum
```java
void backtrack(int start, int remaining, List<Integer> current) {
    if (remaining == 0) { result.add(new ArrayList<>(current)); return; }
    if (remaining < 0) return;  // PRUNE
    for (int i = start; i < n; i++) {
        if (i > start && nums[i] == nums[i-1]) continue;  // skip dups
        current.add(nums[i]);
        backtrack(i, remaining - nums[i], current);  // i=reuse, i+1=no reuse
        current.remove(current.size() - 1);
    }
}
```

## Pattern BT.4: N-Queens
```java
void backtrack(int row) {
    if (row == n) { result.add(board); return; }
    for (int col = 0; col < n; col++) {
        if (cols.contains(col) || diags.contains(row-col) || antiDiags.contains(row+col))
            continue;  // PRUNE: conflict
        place(row, col);
        backtrack(row + 1);
        remove(row, col);
    }
}
```

## Optimization Techniques
| Technique | Effect |
|-----------|--------|
| Sort + skip duplicates | Avoid redundant branches |
| Early termination | `if remaining < 0: return` |
| Constraint propagation | Track valid choices per cell (Sudoku) |
| Trie-guided DFS | Only follow valid prefixes (Word Search II) |
| Symmetry breaking | Fix first queen in half the board |
