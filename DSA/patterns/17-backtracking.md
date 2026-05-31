# 17 - Backtracking Patterns

## Core Concept

Backtracking = DFS on a **decision tree**. At each node, make a choice, recurse, then **undo** the choice.

```
backtrack(state):
    if goal_reached(state):
        record(state)
        return
    for choice in choices(state):
        if is_valid(choice, state):
            make(choice, state)
            backtrack(state)
            undo(choice, state)        // BACKTRACK
```

---

## Universal Backtracking Template (Java)

```java
void backtrack(List<List<Integer>> result, List<Integer> path, int[] nums, int start, /*constraints*/) {
    if (goalReached(path)) {
        result.add(new ArrayList<>(path));  // deep copy!
        return;
    }
    for (int i = start; i < nums.length; i++) {
        if (shouldPrune(i, nums, path)) continue;  // pruning
        path.add(nums[i]);                          // choose
        backtrack(result, path, nums, nextStart(i), /*updated constraints*/);
        path.remove(path.size() - 1);               // un-choose
    }
}
```

---

## Decision Flowchart: Which Pattern?

```
Is it asking for all subsets/combinations/permutations?
├─ Subsets (all sizes) ──────────────────→ Pattern 1/2
├─ Fixed size k ─────────────────────────→ Pattern 7
├─ Permutations (order matters) ─────────→ Pattern 3/4
├─ Combinations with target sum ─────────→ Pattern 5/6
├─ Constraint satisfaction (place/fill) ─→ Pattern 8/9
├─ Path finding in grid ─────────────────→ Pattern 10
├─ String partitioning ──────────────────→ Pattern 11
└─ Build valid sequence ─────────────────→ Pattern 12/13

Has duplicates in input?
├─ Yes → Sort first, skip nums[i] == nums[i-1] at same level
└─ No  → Standard template

Can reuse elements?
├─ Yes → recurse with start = i
└─ No  → recurse with start = i + 1
```

---

## Decision Tree Visualizations

### Subsets of [1, 2, 3]

```
                        []
             /          |          \
          [1]          [2]         [3]
         /   \          |
      [1,2] [1,3]    [2,3]
        |
     [1,2,3]

Alternative view (include/exclude at each index):

                         []
                   /            \
            include 1         exclude 1
              [1]                []
           /      \           /      \
      inc 2    exc 2     inc 2    exc 2
      [1,2]    [1]       [2]       []
      / \      / \       / \      / \
   i3  e3   i3  e3    i3  e3   i3  e3
 [123] [12] [13] [1] [23] [2] [3]  []
```

**Every leaf is a valid subset. Total = 2^n leaves.**

### Permutations of [1, 2, 3]

```
                            []
              /              |              \
            [1]             [2]            [3]
          /     \         /     \        /     \
       [1,2]  [1,3]   [2,1]  [2,3]  [3,1]  [3,2]
         |      |        |      |      |      |
      [1,2,3][1,3,2] [2,1,3][2,3,1][3,1,2][3,2,1]

Key difference from subsets:
- Subsets: iterate i = start..n (no revisiting earlier indices)
- Permutations: iterate i = 0..n, skip used[i] == true
```

---

## Pattern 1: Subsets (Power Set)

**Signal**: "Return all subsets", "power set", "all subsequences"

**Key Insight**: At each index, include or exclude. Or equivalently, iterate from `start` to `n` adding each.

```java
public List<List<Integer>> subsets(int[] nums) {
    List<List<Integer>> result = new ArrayList<>();
    backtrack(result, new ArrayList<>(), nums, 0);
    return result;
}

private void backtrack(List<List<Integer>> result, List<Integer> path, int[] nums, int start) {
    result.add(new ArrayList<>(path));  // every node is a valid subset
    for (int i = start; i < nums.length; i++) {
        path.add(nums[i]);
        backtrack(result, path, nums, i + 1);
        path.remove(path.size() - 1);
    }
}
```

**Complexity**: O(n * 2^n) time, O(n) recursion depth

---

## Pattern 2: Subsets II (With Duplicates)

**Signal**: "Input has duplicates", "unique subsets only"

**Key Insight**: Sort first. At same recursion level, skip `nums[i] == nums[i-1]`.

```java
public List<List<Integer>> subsetsWithDup(int[] nums) {
    Arrays.sort(nums);  // CRITICAL
    List<List<Integer>> result = new ArrayList<>();
    backtrack(result, new ArrayList<>(), nums, 0);
    return result;
}

private void backtrack(List<List<Integer>> result, List<Integer> path, int[] nums, int start) {
    result.add(new ArrayList<>(path));
    for (int i = start; i < nums.length; i++) {
        if (i > start && nums[i] == nums[i - 1]) continue;  // skip dups at same level
        path.add(nums[i]);
        backtrack(result, path, nums, i + 1);
        path.remove(path.size() - 1);
    }
}
```

**Why `i > start`?** We only skip if it's not the first choice at this level. The first occurrence is always valid; subsequent identical values at the same branching level produce duplicate subtrees.

```
nums = [1, 2, 2]  sorted
Level at start=1:  i=1 picks 2 ✓,  i=2 picks 2 ✗ (i > start && nums[2]==nums[1])
```

---

## Pattern 3: Permutations

**Signal**: "All orderings", "arrangements", "order matters"

**Key Insight**: Every element can be at every position. Use `used[]` to track what's taken.

```java
public List<List<Integer>> permute(int[] nums) {
    List<List<Integer>> result = new ArrayList<>();
    backtrack(result, new ArrayList<>(), nums, new boolean[nums.length]);
    return result;
}

private void backtrack(List<List<Integer>> result, List<Integer> path, int[] nums, boolean[] used) {
    if (path.size() == nums.length) {
        result.add(new ArrayList<>(path));
        return;
    }
    for (int i = 0; i < nums.length; i++) {
        if (used[i]) continue;
        used[i] = true;
        path.add(nums[i]);
        backtrack(result, path, nums, used);
        path.remove(path.size() - 1);
        used[i] = false;
    }
}
```

**Complexity**: O(n! * n) time, O(n) space

---

## Pattern 4: Permutations II (With Duplicates)

**Signal**: "Permutations with duplicate elements", "unique permutations"

**Key Insight**: Sort + skip when `nums[i] == nums[i-1] && !used[i-1]`.

```java
public List<List<Integer>> permuteUnique(int[] nums) {
    Arrays.sort(nums);
    List<List<Integer>> result = new ArrayList<>();
    backtrack(result, new ArrayList<>(), nums, new boolean[nums.length]);
    return result;
}

private void backtrack(List<List<Integer>> result, List<Integer> path, int[] nums, boolean[] used) {
    if (path.size() == nums.length) {
        result.add(new ArrayList<>(path));
        return;
    }
    for (int i = 0; i < nums.length; i++) {
        if (used[i]) continue;
        // Skip: same value as previous AND previous not used (same level duplicate)
        if (i > 0 && nums[i] == nums[i - 1] && !used[i - 1]) continue;
        used[i] = true;
        path.add(nums[i]);
        backtrack(result, path, nums, used);
        path.remove(path.size() - 1);
        used[i] = false;
    }
}
```

**Why `!used[i-1]`?** If `used[i-1]` is true, the duplicate is being used at a higher level (valid). If `used[i-1]` is false, we're at the same level trying the same value again (duplicate subtree).

---

## Pattern 5: Combination Sum (Reuse Allowed)

**Signal**: "Candidates can be used unlimited times", "find combinations summing to target"

**Key Insight**: Recurse with `start = i` (not `i+1`) to allow reuse.

```java
public List<List<Integer>> combinationSum(int[] candidates, int target) {
    Arrays.sort(candidates);  // enables pruning
    List<List<Integer>> result = new ArrayList<>();
    backtrack(result, new ArrayList<>(), candidates, target, 0);
    return result;
}

private void backtrack(List<List<Integer>> result, List<Integer> path, int[] candidates, int remain, int start) {
    if (remain == 0) {
        result.add(new ArrayList<>(path));
        return;
    }
    for (int i = start; i < candidates.length; i++) {
        if (candidates[i] > remain) break;  // PRUNE (requires sorted input)
        path.add(candidates[i]);
        backtrack(result, path, candidates, remain - candidates[i], i);  // i, not i+1
        path.remove(path.size() - 1);
    }
}
```

---

## Pattern 6: Combination Sum II (No Reuse, Duplicates in Input)

**Signal**: "Each number used once", "candidates have duplicates"

**Key Insight**: `start = i + 1` (no reuse) + sort + skip dups at same level.

```java
private void backtrack(List<List<Integer>> result, List<Integer> path, int[] candidates, int remain, int start) {
    if (remain == 0) {
        result.add(new ArrayList<>(path));
        return;
    }
    for (int i = start; i < candidates.length; i++) {
        if (candidates[i] > remain) break;
        if (i > start && candidates[i] == candidates[i - 1]) continue;  // skip dups
        path.add(candidates[i]);
        backtrack(result, path, candidates, remain - candidates[i], i + 1);  // i+1
        path.remove(path.size() - 1);
    }
}
```

---

## Pattern 7: Combinations (Choose k from n)

**Signal**: "Choose k numbers from 1..n", "C(n,k)"

```java
public List<List<Integer>> combine(int n, int k) {
    List<List<Integer>> result = new ArrayList<>();
    backtrack(result, new ArrayList<>(), n, k, 1);
    return result;
}

private void backtrack(List<List<Integer>> result, List<Integer> path, int n, int k, int start) {
    if (path.size() == k) {
        result.add(new ArrayList<>(path));
        return;
    }
    // Pruning: need (k - path.size()) more elements, so stop when not enough remain
    for (int i = start; i <= n - (k - path.size()) + 1; i++) {
        path.add(i);
        backtrack(result, path, n, k, i + 1);
        path.remove(path.size() - 1);
    }
}
```

**Pruning bound**: `i <= n - (k - path.size()) + 1` ensures enough elements remain.

**Complexity**: O(k * C(n,k))

---

## Pattern 8: N-Queens

**Signal**: "Place N queens on NxN board with no attacks"

**Key Insight**: Place row by row. Track occupied columns, diagonals (`row-col`), anti-diagonals (`row+col`).

```java
public List<List<String>> solveNQueens(int n) {
    List<List<String>> result = new ArrayList<>();
    Set<Integer> cols = new HashSet<>();
    Set<Integer> diags = new HashSet<>();      // row - col
    Set<Integer> antiDiags = new HashSet<>();   // row + col
    backtrack(result, new ArrayList<>(), n, 0, cols, diags, antiDiags);
    return result;
}

private void backtrack(List<List<String>> result, List<String> board, int n, int row,
                       Set<Integer> cols, Set<Integer> diags, Set<Integer> antiDiags) {
    if (row == n) {
        result.add(new ArrayList<>(board));
        return;
    }
    for (int col = 0; col < n; col++) {
        if (cols.contains(col) || diags.contains(row - col) || antiDiags.contains(row + col))
            continue;
        
        char[] rowArr = new char[n];
        Arrays.fill(rowArr, '.');
        rowArr[col] = 'Q';
        
        cols.add(col);
        diags.add(row - col);
        antiDiags.add(row + col);
        board.add(new String(rowArr));
        
        backtrack(result, board, n, row + 1, cols, diags, antiDiags);
        
        board.remove(board.size() - 1);
        cols.remove(col);
        diags.remove(row - col);
        antiDiags.remove(row + col);
    }
}
```

**Why row-by-row?** Only one queen per row, so we just choose which column for each row.

**Complexity**: O(n!) upper bound (heavily pruned)

---

## Pattern 9: Sudoku Solver

**Signal**: "Fill grid satisfying row/col/box constraints"

**Key Insight**: Find next empty cell, try 1-9, validate constraints, recurse. Return boolean to stop after first solution.

```java
public void solveSudoku(char[][] board) {
    solve(board);
}

private boolean solve(char[][] board) {
    for (int r = 0; r < 9; r++) {
        for (int c = 0; c < 9; c++) {
            if (board[r][c] != '.') continue;
            for (char num = '1'; num <= '9'; num++) {
                if (isValid(board, r, c, num)) {
                    board[r][c] = num;
                    if (solve(board)) return true;
                    board[r][c] = '.';  // backtrack
                }
            }
            return false;  // no valid number for this cell → backtrack
        }
    }
    return true;  // all cells filled
}

private boolean isValid(char[][] board, int row, int col, char num) {
    int boxRow = (row / 3) * 3, boxCol = (col / 3) * 3;
    for (int i = 0; i < 9; i++) {
        if (board[row][i] == num) return false;              // row
        if (board[i][col] == num) return false;              // col
        if (board[boxRow + i / 3][boxCol + i % 3] == num) return false;  // box
    }
    return true;
}
```

**Optimization**: Use bitmasks for row/col/box constraints → O(1) validation.

---

## Pattern 10: Word Search (Grid DFS + Backtrack)

**Signal**: "Find word in grid by adjacent cells", "path in matrix"

```java
public boolean exist(char[][] board, String word) {
    int m = board.length, n = board[0].length;
    for (int i = 0; i < m; i++)
        for (int j = 0; j < n; j++)
            if (dfs(board, word, i, j, 0)) return true;
    return false;
}

private boolean dfs(char[][] board, String word, int r, int c, int idx) {
    if (idx == word.length()) return true;
    if (r < 0 || r >= board.length || c < 0 || c >= board[0].length) return false;
    if (board[r][c] != word.charAt(idx)) return false;
    
    char temp = board[r][c];
    board[r][c] = '#';  // mark visited (in-place backtrack)
    
    boolean found = dfs(board, word, r + 1, c, idx + 1)
                 || dfs(board, word, r - 1, c, idx + 1)
                 || dfs(board, word, r, c + 1, idx + 1)
                 || dfs(board, word, r, c - 1, idx + 1);
    
    board[r][c] = temp;  // restore
    return found;
}
```

**Complexity**: O(m * n * 4^L) where L = word length

---

## Pattern 11: Palindrome Partitioning

**Signal**: "Partition string so every segment is palindrome"

**Key Insight**: At each position, try all possible cut lengths. If prefix is palindrome, recurse on remainder.

```java
public List<List<String>> partition(String s) {
    List<List<String>> result = new ArrayList<>();
    backtrack(result, new ArrayList<>(), s, 0);
    return result;
}

private void backtrack(List<List<String>> result, List<String> path, String s, int start) {
    if (start == s.length()) {
        result.add(new ArrayList<>(path));
        return;
    }
    for (int end = start + 1; end <= s.length(); end++) {
        String segment = s.substring(start, end);
        if (!isPalindrome(segment)) continue;  // prune non-palindromes
        path.add(segment);
        backtrack(result, path, s, end);
        path.remove(path.size() - 1);
    }
}

private boolean isPalindrome(String s) {
    int l = 0, r = s.length() - 1;
    while (l < r) {
        if (s.charAt(l++) != s.charAt(r--)) return false;
    }
    return true;
}
```

**Optimization**: Precompute palindrome DP table `dp[i][j]` for O(1) checks.

---

## Pattern 12: Generate Parentheses

**Signal**: "Generate all valid parentheses combinations", "n pairs"

**Key Insight**: Constraints: `open < n` → can add `(`. `close < open` → can add `)`.

```java
public List<String> generateParenthesis(int n) {
    List<String> result = new ArrayList<>();
    backtrack(result, new StringBuilder(), 0, 0, n);
    return result;
}

private void backtrack(List<String> result, StringBuilder sb, int open, int close, int n) {
    if (sb.length() == 2 * n) {
        result.add(sb.toString());
        return;
    }
    if (open < n) {
        sb.append('(');
        backtrack(result, sb, open + 1, close, n);
        sb.deleteCharAt(sb.length() - 1);
    }
    if (close < open) {
        sb.append(')');
        backtrack(result, sb, open, close + 1, n);
        sb.deleteCharAt(sb.length() - 1);
    }
}
```

**Complexity**: O(4^n / sqrt(n)) — nth Catalan number

---

## Pattern 13: Letter Combinations of Phone Number

**Signal**: "Phone keypad mappings", "all possible letter combinations from digits"

```java
private static final String[] MAPPING = {"", "", "abc", "def", "ghi", "jkl", "mno", "pqrs", "tuv", "wxyz"};

public List<String> letterCombinations(String digits) {
    List<String> result = new ArrayList<>();
    if (digits.isEmpty()) return result;
    backtrack(result, new StringBuilder(), digits, 0);
    return result;
}

private void backtrack(List<String> result, StringBuilder sb, String digits, int idx) {
    if (idx == digits.length()) {
        result.add(sb.toString());
        return;
    }
    String letters = MAPPING[digits.charAt(idx) - '0'];
    for (char c : letters.toCharArray()) {
        sb.append(c);
        backtrack(result, sb, digits, idx + 1);
        sb.deleteCharAt(sb.length() - 1);
    }
}
```

**Complexity**: O(4^n) where n = number of digits (worst case: 7 and 9 have 4 letters)

---

## Pattern 14: Partition to K Equal Sum Subsets

**Signal**: "Divide array into k subsets with equal sum", "multi-bucket assignment"

**Key Insight**: Assign each element to one of k buckets. Prune aggressively.

```java
public boolean canPartitionKSubsets(int[] nums, int k) {
    int sum = Arrays.stream(nums).sum();
    if (sum % k != 0) return false;
    int target = sum / k;
    Arrays.sort(nums);  // sort ascending for pruning
    if (nums[nums.length - 1] > target) return false;
    
    int[] buckets = new int[k];
    return backtrack(nums, buckets, nums.length - 1, target);  // start from largest
}

private boolean backtrack(int[] nums, int[] buckets, int idx, int target) {
    if (idx < 0) return true;  // all elements assigned
    
    Set<Integer> tried = new HashSet<>();  // skip duplicate bucket values
    for (int i = 0; i < buckets.length; i++) {
        if (tried.contains(buckets[i])) continue;  // prune symmetric states
        if (buckets[i] + nums[idx] > target) continue;  // prune overflow
        
        tried.add(buckets[i]);
        buckets[i] += nums[idx];
        if (backtrack(nums, buckets, idx - 1, target)) return true;
        buckets[i] -= nums[idx];
    }
    return false;
}
```

**Critical Optimizations**:
1. Sort descending (large elements first) → fail fast
2. Skip buckets with same current sum → avoid symmetric exploration
3. If `nums[largest] > target` → impossible

**Complexity**: O(k^n) worst case, massively pruned in practice

---

## Optimization Techniques

| Technique | When to Use | Effect |
|-----------|-------------|--------|
| **Sort input** | Duplicates or sum problems | Enables skip logic & early termination |
| **Skip duplicates** | `nums[i] == nums[i-1]` at same level | Eliminates duplicate subtrees |
| **Early termination** | `remain < 0` or `candidates[i] > remain` | Prunes entire subtrees |
| **Bound pruning** | Combinations: not enough elements left | `i <= n - (k - size) + 1` |
| **Symmetry breaking** | K-subsets: identical bucket values | Skip buckets with same sum |
| **Process largest first** | Partition problems | Fail fast on impossible assignments |
| **Constraint propagation** | Sudoku, N-Queens | HashSets for O(1) validity check |
| **In-place marking** | Grid search | `board[r][c] = '#'` avoids visited set |
| **Trie-guided** | Word search with dictionary | Prune paths not in any word prefix |
| **Precompute validity** | Palindrome partitioning | DP table for O(1) palindrome check |
| **Bitmask state** | Small n (< 20) | Replace boolean[] with int bitmask |

---

## Time Complexity Analysis

**How to calculate backtracking complexity:**

```
T = (branching factor)^(depth) × (work per node)
```

| Pattern | Branching | Depth | Per Node | Total |
|---------|-----------|-------|----------|-------|
| Subsets | 2 (include/exclude) | n | O(n) copy | O(n * 2^n) |
| Permutations | n, n-1, n-2... | n | O(n) copy | O(n * n!) |
| Combination Sum | up to n | target/min | O(n) copy | O(n^(T/M)) |
| N-Queens | n (cols) | n (rows) | O(1) with sets | O(n!) |
| Sudoku | 9 | 81 empty cells | O(1) with bitmask | O(9^m), m=empties |
| Word Search | 4 (directions) | L (word len) | O(1) | O(m*n*4^L) |
| Parentheses | 2 (open/close) | 2n | O(n) copy | O(4^n/sqrt(n)) |
| K-Subsets | k (buckets) | n (elements) | O(1) | O(k^n) |

---

## Common Mistakes

1. **Forgetting deep copy**: `result.add(path)` stores a reference. Always `new ArrayList<>(path)`.
2. **Wrong start index**: Subsets/combinations use `start`, permutations use `0 + used[]`.
3. **Duplicate skip condition**: Must be `i > start` (not `i > 0`) for subset-style. Must check `!used[i-1]` for permutation-style.
4. **Not sorting before dedup**: Skip logic requires sorted input.
5. **Missing base case return**: Forgetting `return false` after trying all options in constraint problems (Sudoku).

---

## Pattern Recognition Summary

```
┌─────────────────────────────────────────────────────────────┐
│  "All subsets"           → start=i+1, collect at every node │
│  "All permutations"     → start=0, used[], collect at leaf │
│  "Combinations of size k"→ start=i+1, collect when size==k │
│  "Sum equals target"    → start=i(reuse)/i+1, prune > tgt  │
│  "With duplicates"      → sort + skip same value same level │
│  "Place on board"       → row by row, constraint sets       │
│  "Find in grid"         → 4-dir DFS, mark/unmark visited   │
│  "Partition string"     → try all prefix lengths, validate  │
│  "Build valid sequence" → track constraints (open/close)    │
│  "Divide into k groups" → assign each element to a bucket  │
└─────────────────────────────────────────────────────────────┘
```
