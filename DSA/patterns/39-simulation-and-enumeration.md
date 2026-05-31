# Pattern 39: Simulation, Counting, and Enumeration

## Decision Flowchart

```
Problem involves step-by-step process?
├─ YES: Can you find a closed-form/math shortcut?
│   ├─ YES → Use math (O(1) or O(log n))
│   └─ NO → Simulate directly
│       ├─ State depends on neighbors? → State Machine / Grid Simulation
│       ├─ Circular/periodic? → Clock/Circular (detect cycle length)
│       └─ Sequential process? → Process Simulation
├─ "How many X satisfy Y?"
│   ├─ Can decompose into independent contributions? → Contribution Technique
│   ├─ Subarray/substring condition? → Prefix Sum / Sliding Window
│   ├─ Pairs with property? → Sort + Two Pointer / HashMap counting
│   └─ All subsets/permutations needed? → Enumeration (watch constraints!)
└─ Brainteaser? → Find the mathematical invariant
```

### Complexity Awareness: Enumeration Limits

| Approach | Complexity | Max n (1s) |
|----------|-----------|------------|
| All pairs | O(n²) | ~10⁴ |
| All triplets | O(n³) | ~500 |
| All subsets | O(2ⁿ) | ~20-25 |
| All permutations | O(n!) | ~10-11 |
| All partitions | O(Bell(n)) | ~15 |

**Rule**: If n > threshold, a math/DP shortcut MUST exist. Don't brute-force.

---

## 1. Direct Simulation

### Signal
- Problem describes a physical/mechanical process step by step
- "Simulate what happens when..."
- No shortcut apparent; constraints are small enough (n ≤ 10⁴)

### Template: Spiral Matrix Traversal

```java
public List<Integer> spiralOrder(int[][] matrix) {
    List<Integer> result = new ArrayList<>();
    if (matrix.length == 0) return result;
    
    int top = 0, bottom = matrix.length - 1;
    int left = 0, right = matrix[0].length - 1;
    
    while (top <= bottom && left <= right) {
        // Traverse right
        for (int col = left; col <= right; col++)
            result.add(matrix[top][col]);
        top++;
        
        // Traverse down
        for (int row = top; row <= bottom; row++)
            result.add(matrix[row][right]);
        right--;
        
        // Traverse left
        if (top <= bottom) {
            for (int col = right; col >= left; col--)
                result.add(matrix[bottom][col]);
            bottom--;
        }
        
        // Traverse up
        if (left <= right) {
            for (int row = bottom; row >= top; row--)
                result.add(matrix[row][left]);
            left++;
        }
    }
    return result;
}
```

### Template: Asteroid Collision

```java
public int[] asteroidCollision(int[] asteroids) {
    Deque<Integer> stack = new ArrayDeque<>();
    
    for (int ast : asteroids) {
        boolean destroyed = false;
        // Collision: stack top moving right (+), current moving left (-)
        while (!stack.isEmpty() && stack.peek() > 0 && ast < 0) {
            int top = stack.peek();
            if (top < -ast) {
                stack.pop(); // top destroyed, continue checking
            } else if (top == -ast) {
                stack.pop(); // both destroyed
                destroyed = true;
                break;
            } else {
                destroyed = true; // current destroyed
                break;
            }
        }
        if (!destroyed) stack.push(ast);
    }
    
    int[] res = new int[stack.size()];
    for (int i = res.length - 1; i >= 0; i--) res[i] = stack.pop();
    return res;
}
```

### Template: Robot Bounded in Circle

```java
public boolean isRobotBounded(String instructions) {
    // Direction: 0=N, 1=E, 2=S, 3=W
    int[][] dirs = {{0,1},{1,0},{0,-1},{-1,0}};
    int x = 0, y = 0, d = 0;
    
    for (char c : instructions.toCharArray()) {
        if (c == 'G') { x += dirs[d][0]; y += dirs[d][1]; }
        else if (c == 'L') d = (d + 3) % 4;
        else d = (d + 1) % 4;
    }
    // Bounded if: back at origin OR not facing north
    return (x == 0 && y == 0) || d != 0;
}
```

**Math insight**: After one pass, if direction != North, after 4 passes robot returns to origin. This is the shortcut that avoids simulating multiple cycles.

### Visualization: Spiral Matrix

```
Boundaries shrink inward each layer:

    left        right
     ↓            ↓
→ → → → → → → → →   ← top
                  ↓
↑                 ↓
↑                 ↓
↑                 ↓
↑ ← ← ← ← ← ← ←   ← bottom

After one layer: top++, bottom--, left++, right--
```

---

## 2. State Machine Simulation

### Signal
- Entity transitions between discrete states based on rules
- Current state + input → next state
- "Design a system that responds to events"

### Template: Game of Life (In-Place with Encoding)

```java
public void gameOfLife(int[][] board) {
    int m = board.length, n = board[0].length;
    // Encode: bit1 = next state, bit0 = current state
    // 0→0: 0, 1→0: 1, 0→1: 2, 1→1: 3
    int[] dx = {-1,-1,-1,0,0,1,1,1};
    int[] dy = {-1,0,1,-1,1,-1,0,1};
    
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            int liveNeighbors = 0;
            for (int k = 0; k < 8; k++) {
                int ni = i + dx[k], nj = j + dy[k];
                if (ni >= 0 && ni < m && nj >= 0 && nj < n)
                    liveNeighbors += board[ni][nj] & 1; // current state
            }
            
            int curr = board[i][j] & 1;
            if (curr == 1 && (liveNeighbors == 2 || liveNeighbors == 3))
                board[i][j] = 3; // stay alive
            else if (curr == 0 && liveNeighbors == 3)
                board[i][j] = 2; // become alive
            // else: dies or stays dead (next bit stays 0)
        }
    }
    
    // Extract next state
    for (int i = 0; i < m; i++)
        for (int j = 0; j < n; j++)
            board[i][j] >>= 1;
}
```

### Template: String Compression (State Machine)

```java
public int compress(char[] chars) {
    int write = 0, read = 0;
    
    while (read < chars.length) {
        char current = chars[read];
        int count = 0;
        
        // State: counting consecutive same chars
        while (read < chars.length && chars[read] == current) {
            read++;
            count++;
        }
        
        // State: writing result
        chars[write++] = current;
        if (count > 1) {
            for (char c : String.valueOf(count).toCharArray())
                chars[write++] = c;
        }
    }
    return write;
}
```

### Template: ATM / Vending Machine State Pattern

```java
class ATM {
    enum State { IDLE, CARD_INSERTED, PIN_ENTERED, TRANSACTION }
    private State state = State.IDLE;
    private int balance;
    
    public String process(String event, int value) {
        switch (state) {
            case IDLE:
                if (event.equals("INSERT_CARD")) {
                    state = State.CARD_INSERTED;
                    return "Enter PIN";
                }
                return "Insert card first";
                
            case CARD_INSERTED:
                if (event.equals("ENTER_PIN") && validatePin(value)) {
                    state = State.PIN_ENTERED;
                    return "Select transaction";
                }
                state = State.IDLE;
                return "Invalid PIN, card ejected";
                
            case PIN_ENTERED:
                if (event.equals("WITHDRAW")) {
                    state = State.TRANSACTION;
                    return processWithdrawal(value);
                }
                break;
                
            case TRANSACTION:
                state = State.IDLE;
                return "Transaction complete";
        }
        return "Invalid operation";
    }
}
```

---

## 3. Clock/Circular Simulation

### Signal
- Elements arranged in a circle
- Process eliminates/visits in circular order
- Modular arithmetic is the key tool

### Template: Josephus Problem

```java
// O(n) iterative solution
public int josephus(int n, int k) {
    int survivor = 0; // base case: 1 person, index 0
    for (int i = 2; i <= n; i++) {
        survivor = (survivor + k) % i;
    }
    return survivor + 1; // 1-indexed
}

// Recursive: J(n,k) = (J(n-1,k) + k) % n, J(1,k) = 0
```

### Template: Gas Station (Circular Greedy)

```java
public int canCompleteCircuit(int[] gas, int[] cost) {
    int totalSurplus = 0, currentSurplus = 0, start = 0;
    
    for (int i = 0; i < gas.length; i++) {
        int net = gas[i] - cost[i];
        totalSurplus += net;
        currentSurplus += net;
        
        if (currentSurplus < 0) {
            // Can't start from any station in [start, i]
            start = i + 1;
            currentSurplus = 0;
        }
    }
    return totalSurplus >= 0 ? start : -1;
}
```

**Math insight**: If total gas >= total cost, a solution exists. The greedy start point is where running surplus last went negative + 1.

### Template: Circular Queue

```java
class CircularQueue {
    int[] data;
    int head, tail, size, capacity;
    
    public CircularQueue(int k) {
        data = new int[k];
        capacity = k;
    }
    
    public boolean enqueue(int value) {
        if (size == capacity) return false;
        data[tail] = value;
        tail = (tail + 1) % capacity;
        size++;
        return true;
    }
    
    public boolean dequeue() {
        if (size == 0) return false;
        head = (head + 1) % capacity;
        size--;
        return true;
    }
}
```

### Visualization: Josephus (n=7, k=3)

```
Round:  Kill position (0-indexed in remaining):

[0,1,2,3,4,5,6]  → kill index 2 → remove 2
[0,1,3,4,5,6]    → kill index 4 → remove 5  (start from 3, count 3: 3,4,5)
[0,1,3,4,6]      → kill index 3 → remove 4  (start from 6, count 3: 6,0,1... wait)

Formula works backwards: survivor(1)=0, survivor(i) = (survivor(i-1)+k)%i
```

---

## 4. Grid Simulation

### Signal
- 2D grid with cells that update based on neighbor states
- "Click to reveal" mechanics (Minesweeper)
- Cellular automata rules

### Template: Minesweeper Click Reveal

```java
public char[][] updateBoard(char[][] board, int[] click) {
    int r = click[0], c = click[1];
    
    if (board[r][c] == 'M') { // Hit a mine
        board[r][c] = 'X';
        return board;
    }
    
    reveal(board, r, c);
    return board;
}

private void reveal(char[][] board, int r, int c) {
    int m = board.length, n = board[0].length;
    if (r < 0 || r >= m || c < 0 || c >= n || board[r][c] != 'E') return;
    
    // Count adjacent mines
    int mines = 0;
    for (int dr = -1; dr <= 1; dr++)
        for (int dc = -1; dc <= 1; dc++) {
            int nr = r + dr, nc = c + dc;
            if (nr >= 0 && nr < m && nc >= 0 && nc < n && board[nr][nc] == 'M')
                mines++;
        }
    
    if (mines > 0) {
        board[r][c] = (char) ('0' + mines);
    } else {
        board[r][c] = 'B'; // blank, recurse to neighbors
        for (int dr = -1; dr <= 1; dr++)
            for (int dc = -1; dc <= 1; dc++)
                if (dr != 0 || dc != 0)
                    reveal(board, r + dr, c + dc);
    }
}
```

---

## 5. Process Simulation

### Signal
- Tasks with constraints (cooldown, priority, resource limits)
- "Schedule tasks to minimize time"
- Queue-based execution models

### Template: Task Scheduler (LC 621)

```java
public int leastInterval(char[] tasks, int n) {
    int[] freq = new int[26];
    for (char t : tasks) freq[t - 'A']++;
    
    int maxFreq = 0, maxCount = 0;
    for (int f : freq) {
        if (f > maxFreq) { maxFreq = f; maxCount = 1; }
        else if (f == maxFreq) maxCount++;
    }
    
    // Math formula: (maxFreq-1) * (n+1) + maxCount
    // But answer is at least tasks.length (no idle needed if spread out)
    int formulaResult = (maxFreq - 1) * (n + 1) + maxCount;
    return Math.max(formulaResult, tasks.length);
}
```

**Visualization**:
```
Tasks: A=3, B=3, C=1, n=2

A B C A B _ A B
|---| |---| |--|
 n+1   n+1  tail

Formula: (3-1)*(2+1) + 2 = 8
         (maxF-1)*(n+1) + countOfMax
```

### Template: LRU Cache Simulation

```java
class LRUCache {
    int capacity;
    LinkedHashMap<Integer, Integer> map;
    
    public LRUCache(int capacity) {
        this.capacity = capacity;
        // accessOrder=true makes it LRU-ordered
        map = new LinkedHashMap<>(capacity, 0.75f, true) {
            protected boolean removeEldestEntry(Map.Entry eldest) {
                return size() > LRUCache.this.capacity;
            }
        };
    }
    
    public int get(int key) {
        return map.getOrDefault(key, -1);
    }
    
    public void put(int key, int value) {
        map.put(key, value);
    }
}
```

---

## 6. Counting Patterns

### 6a. Count Pairs/Triplets with Property

**Signal**: "How many pairs (i,j) satisfy condition?"

```java
// Count pairs with sum == target using HashMap
public int countPairs(int[] nums, int target) {
    Map<Integer, Integer> freq = new HashMap<>();
    int count = 0;
    
    for (int num : nums) {
        int complement = target - num;
        count += freq.getOrDefault(complement, 0);
        freq.merge(num, 1, Integer::sum);
    }
    return count;
}

// Count triplets: fix one element, reduce to pair problem → O(n²)
public int countTriplets(int[] nums, int target) {
    Arrays.sort(nums);
    int count = 0;
    for (int i = 0; i < nums.length - 2; i++) {
        int lo = i + 1, hi = nums.length - 1;
        while (lo < hi) {
            int sum = nums[i] + nums[lo] + nums[hi];
            if (sum == target) {
                // Handle duplicates carefully
                if (nums[lo] == nums[hi]) {
                    int range = hi - lo + 1;
                    count += range * (range - 1) / 2;
                    break;
                }
                int leftCount = 1, rightCount = 1;
                while (lo + leftCount < hi && nums[lo + leftCount] == nums[lo]) leftCount++;
                while (hi - rightCount > lo && nums[hi - rightCount] == nums[hi]) rightCount++;
                count += leftCount * rightCount;
                lo += leftCount;
                hi -= rightCount;
            } else if (sum < target) lo++;
            else hi--;
        }
    }
    return count;
}
```

### 6b. Count Subarrays with Condition

**Three main techniques:**

```java
// Technique 1: Prefix Sum (subarrays with sum == k)
public int subarraySum(int[] nums, int k) {
    Map<Integer, Integer> prefixCount = new HashMap<>();
    prefixCount.put(0, 1);
    int sum = 0, count = 0;
    
    for (int num : nums) {
        sum += num;
        count += prefixCount.getOrDefault(sum - k, 0);
        prefixCount.merge(sum, 1, Integer::sum);
    }
    return count;
}

// Technique 2: Sliding Window (subarrays with at most k distinct)
// Count(exactly k) = Count(atMost k) - Count(atMost k-1)
public int subarraysWithAtMost(int[] nums, int k) {
    Map<Integer, Integer> freq = new HashMap<>();
    int left = 0, count = 0;
    
    for (int right = 0; right < nums.length; right++) {
        freq.merge(nums[right], 1, Integer::sum);
        
        while (freq.size() > k) {
            int leftVal = nums[left];
            freq.merge(leftVal, -1, Integer::sum);
            if (freq.get(leftVal) == 0) freq.remove(leftVal);
            left++;
        }
        count += right - left + 1; // all subarrays ending at right
    }
    return count;
}

// Technique 3: Contribution (covered in Section 8)
```

### 6c. Count Paths in Grid/Tree

```java
// Grid paths (obstacles): DP
public int uniquePathsWithObstacles(int[][] grid) {
    int m = grid.length, n = grid[0].length;
    int[] dp = new int[n];
    dp[0] = grid[0][0] == 0 ? 1 : 0;
    
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            if (grid[i][j] == 1) { dp[j] = 0; continue; }
            if (j > 0) dp[j] += dp[j - 1];
        }
    }
    return dp[n - 1];
}

// Tree paths with target sum (prefix sum on path)
public int pathSum(TreeNode root, long target) {
    Map<Long, Integer> prefixMap = new HashMap<>();
    prefixMap.put(0L, 1);
    return dfs(root, 0, target, prefixMap);
}

private int dfs(TreeNode node, long currSum, long target, Map<Long, Integer> prefixMap) {
    if (node == null) return 0;
    currSum += node.val;
    int count = prefixMap.getOrDefault(currSum - target, 0);
    prefixMap.merge(currSum, 1, Integer::sum);
    count += dfs(node.left, currSum, target, prefixMap);
    count += dfs(node.right, currSum, target, prefixMap);
    prefixMap.merge(currSum, -1, Integer::sum); // backtrack
    return count;
}
```

---

## 7. Enumeration Patterns

### 7a. Enumerate All Pairs O(n²)

```java
// Use when n ≤ 10⁴ and no sorting/hash trick works
public List<int[]> enumeratePairs(int[] nums, Predicate<int[]> condition) {
    List<int[]> result = new ArrayList<>();
    for (int i = 0; i < nums.length; i++)
        for (int j = i + 1; j < nums.length; j++)
            if (condition.test(new int[]{nums[i], nums[j]}))
                result.add(new int[]{i, j});
    return result;
}
```

### 7b. Enumerate All Subsets O(2^n)

```java
// Bitmask enumeration (n ≤ 20)
public List<List<Integer>> subsets(int[] nums) {
    int n = nums.length;
    List<List<Integer>> result = new ArrayList<>();
    
    for (int mask = 0; mask < (1 << n); mask++) {
        List<Integer> subset = new ArrayList<>();
        for (int i = 0; i < n; i++)
            if ((mask & (1 << i)) != 0)
                subset.add(nums[i]);
        result.add(subset);
    }
    return result;
}

// Subset sum check with bitmask
public boolean canPartition(int[] nums, int target) {
    int n = nums.length;
    for (int mask = 0; mask < (1 << n); mask++) {
        int sum = 0;
        for (int i = 0; i < n; i++)
            if ((mask & (1 << i)) != 0)
                sum += nums[i];
        if (sum == target) return true;
    }
    return false;
}
```

### 7c. Enumerate All Permutations O(n!)

```java
// Backtracking (n ≤ 10)
public List<List<Integer>> permute(int[] nums) {
    List<List<Integer>> result = new ArrayList<>();
    backtrack(nums, new boolean[nums.length], new ArrayList<>(), result);
    return result;
}

private void backtrack(int[] nums, boolean[] used, List<Integer> path, List<List<Integer>> result) {
    if (path.size() == nums.length) {
        result.add(new ArrayList<>(path));
        return;
    }
    for (int i = 0; i < nums.length; i++) {
        if (used[i]) continue;
        used[i] = true;
        path.add(nums[i]);
        backtrack(nums, used, path, result);
        path.remove(path.size() - 1);
        used[i] = false;
    }
}
```

### 7d. Enumerate Splits/Partitions

```java
// Enumerate all ways to split array into k contiguous parts
public void enumerateSplits(int[] nums, int k, List<List<int[]>> result) {
    // Place k-1 dividers among n-1 gaps
    // For k=2: try every split point
    if (k == 2) {
        for (int i = 1; i < nums.length; i++) {
            // left = [0, i), right = [i, n)
            processSplit(nums, i);
        }
    }
    // General: use combination of k-1 positions from n-1 gaps
}

// Partition into non-contiguous groups: Stirling numbers
// Use backtracking for small n
```

---

## 8. Contribution Technique

### Signal
- "Sum of [min/max/sum] of all subarrays/subsets"
- Instead of iterating all subarrays (O(n²) or O(2^n)), ask: "How much does element i contribute?"

### Template: Sum of Subarray Minimums (LC 907)

```java
public int sumSubarrayMins(int[] arr) {
    int MOD = 1_000_000_007;
    int n = arr.length;
    long result = 0;
    
    // For each element: how many subarrays is it the minimum of?
    // Find: left[i] = distance to previous smaller element
    //        right[i] = distance to next smaller-or-equal element
    int[] left = new int[n], right = new int[n];
    Deque<Integer> stack = new ArrayDeque<>();
    
    // Previous Less Element
    for (int i = 0; i < n; i++) {
        while (!stack.isEmpty() && arr[stack.peek()] >= arr[i])
            stack.pop();
        left[i] = stack.isEmpty() ? i + 1 : i - stack.peek();
        stack.push(i);
    }
    
    stack.clear();
    
    // Next Less Element (strictly less to avoid double-counting)
    for (int i = n - 1; i >= 0; i--) {
        while (!stack.isEmpty() && arr[stack.peek()] > arr[i])
            stack.pop();
        right[i] = stack.isEmpty() ? n - i : stack.peek() - i;
        stack.push(i);
    }
    
    for (int i = 0; i < n; i++) {
        result = (result + (long) arr[i] * left[i] % MOD * right[i]) % MOD;
    }
    return (int) result;
}
```

### Visualization: Contribution Counting

```
arr = [3, 1, 2, 4]

For element 1 (index 1):
  Left boundary: no smaller to the left → left[1] = 2 (indices 0,1)
  Right boundary: no smaller to the right → right[1] = 3 (indices 1,2,3)
  
  Subarrays where 1 is minimum: left[1] * right[1] = 2 * 3 = 6
  Contribution: 1 * 6 = 6
  
  These subarrays: [3,1], [1], [3,1,2], [1,2], [3,1,2,4], [1,2,4]
  All have min = 1 ✓
```

### Template: Sum of Subarray Ranges (Max - Min for all subarrays)

```java
// = SumOfSubarrayMaximums - SumOfSubarrayMinimums
// Apply contribution technique twice: once for max, once for min
public long subArrayRanges(int[] nums) {
    return sumSubarrayMaxs(nums) - sumSubarrayMins(nums);
}
```

### Contribution in Subset Problems

```java
// Sum of XOR of all subsets
// Each bit position: if k numbers have that bit set,
// then 2^(k) * 2^(n-k) - 2^(n-k) * 2^(k-1)... 
// Actually: bit contributes to 2^(n-1) subsets (half of all non-empty)
// if at least one element has that bit set

// Sum of OR of all subsets: bit b contributes 2^b * (2^n - 2^(n-count_b))
// where count_b = elements WITHOUT bit b set
```

---

## 9. Digit Enumeration

### Signal
- "Count occurrences of digit d in numbers 1 to n"
- "How many numbers in [L,R] satisfy digit property?"
- Use **Digit DP** or positional analysis

### Template: Count Digit d in [1, n]

```java
// Count occurrences of digit d (1-9) in all numbers from 1 to n
public int countDigit(int n, int d) {
    int count = 0;
    
    for (long place = 1; place <= n; place *= 10) {
        long higher = n / (place * 10);
        long current = (n / place) % 10;
        long lower = n % place;
        
        if (current > d)
            count += (higher + 1) * place;
        else if (current == d)
            count += higher * place + lower + 1;
        else
            count += higher * place;
    }
    return count;
}

// For d=0, adjust: higher starts contributing from place=10 onward
// (no leading zeros)
```

### Template: Digit DP (Count numbers in [0,n] with property)

```java
// Framework: count numbers ≤ n with no repeated digits
public int countSpecialNumbers(int n) {
    char[] digits = String.valueOf(n).toCharArray();
    int len = digits.length;
    // dp[pos][mask][tight][started]
    Integer[][][][] memo = new Integer[len][1 << 10][2][2];
    return dp(digits, 0, 0, true, false, memo);
}

private int dp(char[] digits, int pos, int mask, boolean tight, boolean started, Integer[][][][] memo) {
    if (pos == digits.length) return started ? 1 : 0;
    int t = tight ? 1 : 0, s = started ? 1 : 0;
    if (memo[pos][mask][t][s] != null) return memo[pos][mask][t][s];
    
    int limit = tight ? digits[pos] - '0' : 9;
    int count = 0;
    
    for (int d = 0; d <= limit; d++) {
        if (started && (mask & (1 << d)) != 0) continue; // digit used
        
        boolean newStarted = started || d > 0;
        int newMask = newStarted ? mask | (1 << d) : 0;
        boolean newTight = tight && (d == limit);
        
        count += dp(digits, pos + 1, newMask, newTight, newStarted, memo);
    }
    
    return memo[pos][mask][t][s] = count;
}
```

### Visualization: Counting digit 2 in [1, 315]

```
Position:  hundreds   tens   ones
           (place=100) (10)  (1)

For place=10 (tens digit):
  higher = 315/100 = 3
  current = (315/10)%10 = 1
  lower = 315%10 = 5
  
  current(1) < d(2): count += higher * place = 3 * 10 = 30
  (ranges: 020-029, 120-129, 220-229)
```

---

## 10. Brainteaser Problems

### Signal
- Constraint is too large for simulation (n up to 10⁹)
- Problem has a clean mathematical pattern
- "Find the winner" / "What's the final state?"

### Nim Game

```java
// Two players, remove 1-3 stones. Who wins?
// Insight: Lose iff n % 4 == 0
public boolean canWinNim(int n) {
    return n % 4 != 0;
}
// Why: If n%4==0, whatever you take (1-3), opponent takes (3-1) to make total 4.
//      Opponent always leaves you with a multiple of 4 until you get 0.
```

### Bulb Switcher

```java
// n bulbs, round i toggles every i-th bulb. How many ON after n rounds?
// Insight: Bulb k is toggled once per divisor of k.
//          ON iff odd number of divisors iff k is a perfect square.
public int bulbSwitch(int n) {
    return (int) Math.sqrt(n);
}
```

### Water and Jug Problem

```java
// Can you measure exactly z liters with jugs of x and y liters?
// Insight: Bezout's identity - achievable iff z % gcd(x,y) == 0 and z <= x+y
public boolean canMeasureWater(int x, int y, int z) {
    if (z == 0) return true;
    if (x + y < z) return false;
    return z % gcd(x, y) == 0;
}

private int gcd(int a, int b) { return b == 0 ? a : gcd(b, a % b); }
```

### Power of Two / Three / Four

```java
// Is n a power of 2? (Bit manipulation)
public boolean isPowerOfTwo(int n) {
    return n > 0 && (n & (n - 1)) == 0;
}

// Is n a power of 3? (Largest power of 3 in int range divides n)
public boolean isPowerOfThree(int n) {
    return n > 0 && 1162261467 % n == 0; // 3^19
}
```

### Happy Number (Floyd's Cycle Detection on digit squares)

```java
public boolean isHappy(int n) {
    int slow = n, fast = n;
    do {
        slow = digitSquareSum(slow);
        fast = digitSquareSum(digitSquareSum(fast));
    } while (slow != fast);
    return slow == 1;
}

private int digitSquareSum(int n) {
    int sum = 0;
    while (n > 0) { int d = n % 10; sum += d * d; n /= 10; }
    return sum;
}
```

---

## When to Simulate vs. Use Math

| Scenario | Simulate | Math Shortcut |
|----------|----------|---------------|
| n ≤ 10³, complex rules | Yes | Not worth finding |
| n ≤ 10⁵, simple per-step | Yes (O(n)) | If exists, prefer |
| n ≥ 10⁶ | Too slow | Must find pattern |
| Periodic/cyclic behavior | Detect cycle, then math | Period × full cycles + remainder |
| Game theory (Nim-like) | Only for verification | Grundy numbers / parity |
| Counting problems | Only if n ≤ 20 | DP / combinatorics |

### Finding the Math Shortcut

1. **Simulate small cases** and look for patterns
2. **Check periodicity**: does state repeat? → answer = f(n % period)
3. **Check parity/divisibility**: many game problems reduce to mod arithmetic
4. **Check known sequences**: OEIS, Catalan, Fibonacci, triangular numbers
5. **Invariants**: what quantity is preserved across operations?

---

## Complexity Summary

| Pattern | Time | Space |
|---------|------|-------|
| Spiral Matrix | O(m×n) | O(1) extra |
| Game of Life (in-place) | O(m×n) | O(1) |
| Josephus | O(n) | O(1) |
| Gas Station | O(n) | O(1) |
| Task Scheduler | O(n) | O(1) (26 chars) |
| Count pairs (hash) | O(n) | O(n) |
| Count subarrays (prefix) | O(n) | O(n) |
| Contribution technique | O(n) | O(n) |
| Digit counting | O(log n) | O(1) |
| Subset enumeration | O(2^n) | O(n) |
| Permutation enumeration | O(n!) | O(n) |
| Digit DP | O(log n × states) | O(log n × states) |
| Brainteasers | O(1) | O(1) |

---

## Key Relationships to Other Patterns

- **Contribution Technique** uses **Monotonic Stack** (Pattern 5) for boundary finding
- **Count Subarrays** uses **Sliding Window** (Pattern 3) and **Prefix Sum** (Pattern 2)
- **Digit DP** is a specialized form of **DP** (Patterns 16-20)
- **Process Simulation** often needs **Heap/Priority Queue** (Pattern 7)
- **Circular problems** connect to **Modular Arithmetic** and **Cycle Detection** (Pattern 11)
- **Enumeration** is the brute-force baseline that **Backtracking** (Pattern 14) optimizes with pruning
