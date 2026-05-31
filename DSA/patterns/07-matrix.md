# Pattern 07: Matrix / Grid Patterns

## Decision Flowchart

```
Matrix Problem?
│
├─ Traversal in specific order?
│   ├─ Spiral → Pattern 1: Spiral Traversal
│   ├─ Diagonal → Pattern 8: Diagonal Traversal
│   └─ Layer-by-layer → Spiral variant
│
├─ Transform/Rotate?
│   └─ Pattern 2: Rotate Matrix
│
├─ Search for element?
│   ├─ Each row sorted, first elem > prev row last → Row-major Binary Search
│   └─ Rows sorted, cols sorted independently → Staircase Search
│
├─ Connected components / regions?
│   └─ Pattern 4: Island Problems (BFS/DFS Flood Fill)
│
├─ Optimization (min/max path, count paths)?
│   └─ Pattern 5: Grid DP
│
├─ In-place state marking?
│   ├─ Zero rows/cols → Pattern 6: Set Matrix Zeroes
│   └─ Simultaneous update → Pattern 7: Game of Life
│
├─ Word/path finding with backtracking?
│   └─ Pattern 9: Word Search
│
└─ Linear recurrence acceleration?
    └─ Pattern 10: Matrix Exponentiation
```

---

## Pattern 1: Spiral Traversal

### Signal
- "Print matrix in spiral order"
- "Traverse outside-in layer by layer"
- Generate matrix in spiral fill

### Template (Java)

```java
public List<Integer> spiralOrder(int[][] matrix) {
    List<Integer> result = new ArrayList<>();
    if (matrix.length == 0) return result;
    
    int top = 0, bottom = matrix.length - 1;
    int left = 0, right = matrix[0].length - 1;
    
    while (top <= bottom && left <= right) {
        // → Traverse right along top row
        for (int col = left; col <= right; col++)
            result.add(matrix[top][col]);
        top++;
        
        // ↓ Traverse down along right col
        for (int row = top; row <= bottom; row++)
            result.add(matrix[row][right]);
        right--;
        
        // ← Traverse left along bottom row
        if (top <= bottom) {
            for (int col = right; col >= left; col--)
                result.add(matrix[bottom][col]);
            bottom--;
        }
        
        // ↑ Traverse up along left col
        if (left <= right) {
            for (int row = bottom; row >= top; row--)
                result.add(matrix[row][left]);
            left++;
        }
    }
    return result;
}
```

### Visualization

```
Initial: top=0, bottom=3, left=0, right=3

 →  →  →  →
 ↑  →  →  ↓
 ↑  ↑  ←  ↓
 ↑  ←  ←  ↓       (outer layer)
 
After one loop: top=1, bottom=2, left=1, right=2

          →  →
          ↑  ↓
          ←  ←     (inner layer)
```

### Variants

| Variant | Modification |
|---------|-------------|
| Spiral Matrix II (generate) | Fill `matrix[row][col] = counter++` instead of reading |
| Anti-clockwise spiral | Start going ↓ instead of →: down, right, up, left |
| Spiral from center outward | Start with center coords, expand boundaries |

### Complexity
- **Time:** O(m * n) — every cell visited once
- **Space:** O(1) extra (excluding output)

---

## Pattern 2: Rotate Matrix 90°

### Signal
- "Rotate image/matrix in-place"
- "Transform coordinates"

### Template (Java)

```java
// Rotate 90° clockwise: Transpose + Reverse each row
public void rotate90CW(int[][] matrix) {
    int n = matrix.length;
    
    // Step 1: Transpose (swap matrix[i][j] with matrix[j][i])
    for (int i = 0; i < n; i++)
        for (int j = i + 1; j < n; j++) {
            int tmp = matrix[i][j];
            matrix[i][j] = matrix[j][i];
            matrix[j][i] = tmp;
        }
    
    // Step 2: Reverse each row
    for (int i = 0; i < n; i++) {
        int lo = 0, hi = n - 1;
        while (lo < hi) {
            int tmp = matrix[i][lo];
            matrix[i][lo] = matrix[i][hi];
            matrix[i][hi] = tmp;
            lo++; hi--;
        }
    }
}
```

### Visualization

```
Original:       Transpose:      Reverse rows:
1 2 3           1 4 7           7 4 1
4 5 6    →      2 5 8     →     8 5 2
7 8 9           3 6 9           9 6 3
                                (90° CW result)
```

### All Rotation Variants

| Rotation | Method |
|----------|--------|
| 90° CW | Transpose + Reverse each row |
| 90° CCW | Transpose + Reverse each column (or Reverse rows + Transpose) |
| 180° | Reverse each row + Reverse row order (or rotate 90° twice) |
| Horizontal flip | Reverse each row |
| Vertical flip | Reverse row order |
| Transpose | Swap `[i][j]` ↔ `[j][i]` |
| Anti-transpose | Reverse rows, transpose, reverse rows |

### Coordinate Transform Formula

```
Original (r, c) in n×n matrix:
  90° CW  → (c, n-1-r)
  90° CCW → (n-1-c, r)
  180°    → (n-1-r, n-1-c)
```

### Complexity
- **Time:** O(n²)
- **Space:** O(1) in-place

---

## Pattern 3: Search in Sorted Matrix

### Signal
- "Search in row-sorted and column-sorted matrix"
- "Each row sorted left to right, each column sorted top to bottom"
- "Rows sorted, first element of row > last element of previous row"

### Template A: Row-Major Binary Search (Fully Sorted)

```java
// Matrix where row[i][0] > row[i-1][last] — treat as flattened sorted array
public boolean searchMatrix(int[][] matrix, int target) {
    int m = matrix.length, n = matrix[0].length;
    int lo = 0, hi = m * n - 1;
    
    while (lo <= hi) {
        int mid = lo + (hi - lo) / 2;
        int val = matrix[mid / n][mid % n]; // key conversion
        
        if (val == target) return true;
        else if (val < target) lo = mid + 1;
        else hi = mid - 1;
    }
    return false;
}
```

### Template B: Staircase Search (Row + Col Sorted Independently)

```java
// Each row sorted, each column sorted, but NOT globally sorted
// Start from top-right (or bottom-left)
public boolean searchMatrixII(int[][] matrix, int target) {
    int m = matrix.length, n = matrix[0].length;
    int row = 0, col = n - 1; // start top-right
    
    while (row < m && col >= 0) {
        if (matrix[row][col] == target) return true;
        else if (matrix[row][col] > target) col--; // eliminate column
        else row++; // eliminate row
    }
    return false;
}
```

### Visualization (Staircase)

```
Target = 14, start at top-right corner (15)

 1   4   7  11  [15] ← 15 > 14, move left
 2   5   8  12  [14]   
10  13  14  17   19    
16  18  21  23   25    

 1   4   7 [11]       ← 11 < 14, move down
 2   5   8 [12]       ← 12 < 14, move down
10  13  14 [17]       ← 17 > 14, move left
10  13 [14]           ← Found!
```

### Comparison

| Property | Row-Major BS | Staircase |
|----------|-------------|-----------|
| Precondition | Fully sorted (row-major) | Row-sorted + Col-sorted |
| Time | O(log(m*n)) | O(m + n) |
| Space | O(1) | O(1) |

### Complexity
- **Row-major BS:** O(log(mn)) time, O(1) space
- **Staircase:** O(m + n) time, O(1) space

---

## Pattern 4: Island Problems / Flood Fill

### Signal
- "Count number of islands"
- "Find max area of island"
- "Calculate perimeter"
- "Surrounded regions"
- "Water flow to both oceans"

### Template: Count Islands (DFS)

```java
private static final int[][] DIRS = {{0,1},{0,-1},{1,0},{-1,0}};

public int numIslands(char[][] grid) {
    int m = grid.length, n = grid[0].length;
    int count = 0;
    
    for (int i = 0; i < m; i++)
        for (int j = 0; j < n; j++)
            if (grid[i][j] == '1') {
                count++;
                dfs(grid, i, j, m, n);
            }
    return count;
}

private void dfs(char[][] grid, int r, int c, int m, int n) {
    if (r < 0 || r >= m || c < 0 || c >= n || grid[r][c] != '1') return;
    grid[r][c] = '0'; // mark visited (sink the island)
    for (int[] d : DIRS)
        dfs(grid, r + d[0], c + d[1], m, n);
}
```

### Template: Max Area Island

```java
public int maxAreaOfIsland(int[][] grid) {
    int m = grid.length, n = grid[0].length, max = 0;
    for (int i = 0; i < m; i++)
        for (int j = 0; j < n; j++)
            if (grid[i][j] == 1)
                max = Math.max(max, areaDF(grid, i, j, m, n));
    return max;
}

private int areaDFS(int[][] grid, int r, int c, int m, int n) {
    if (r < 0 || r >= m || c < 0 || c >= n || grid[r][c] != 1) return 0;
    grid[r][c] = 0;
    int area = 1;
    for (int[] d : DIRS)
        area += areaDFS(grid, r + d[0], c + d[1], m, n);
    return area;
}
```

### Template: Island Perimeter

```java
public int islandPerimeter(int[][] grid) {
    int m = grid.length, n = grid[0].length, perimeter = 0;
    for (int i = 0; i < m; i++)
        for (int j = 0; j < n; j++)
            if (grid[i][j] == 1) {
                perimeter += 4;
                // Subtract shared edges
                if (i > 0 && grid[i-1][j] == 1) perimeter -= 2;
                if (j > 0 && grid[i][j-1] == 1) perimeter -= 2;
            }
    return perimeter;
}
```

### Template: Surrounded Regions (Border DFS)

```java
// O on border or connected to border O → safe. Everything else → flip to X.
public void solve(char[][] board) {
    int m = board.length, n = board[0].length;
    
    // Mark border-connected O's as safe ('S')
    for (int i = 0; i < m; i++) {
        if (board[i][0] == 'O') markSafe(board, i, 0, m, n);
        if (board[i][n-1] == 'O') markSafe(board, i, n-1, m, n);
    }
    for (int j = 0; j < n; j++) {
        if (board[0][j] == 'O') markSafe(board, 0, j, m, n);
        if (board[m-1][j] == 'O') markSafe(board, m-1, j, m, n);
    }
    
    // Flip: remaining O → X, S → O
    for (int i = 0; i < m; i++)
        for (int j = 0; j < n; j++) {
            if (board[i][j] == 'O') board[i][j] = 'X';
            else if (board[i][j] == 'S') board[i][j] = 'O';
        }
}

private void markSafe(char[][] board, int r, int c, int m, int n) {
    if (r < 0 || r >= m || c < 0 || c >= n || board[r][c] != 'O') return;
    board[r][c] = 'S';
    for (int[] d : DIRS) markSafe(board, r + d[0], c + d[1], m, n);
}
```

### Template: Pacific Atlantic Water Flow

```java
// Water flows from higher/equal to lower. Find cells that can reach BOTH oceans.
public List<List<Integer>> pacificAtlantic(int[][] heights) {
    int m = heights.length, n = heights[0].length;
    boolean[][] pacific = new boolean[m][n];
    boolean[][] atlantic = new boolean[m][n];
    
    // DFS from Pacific borders (top row + left col)
    for (int i = 0; i < m; i++) dfsOcean(heights, pacific, i, 0, m, n);
    for (int j = 0; j < n; j++) dfsOcean(heights, pacific, 0, j, m, n);
    
    // DFS from Atlantic borders (bottom row + right col)
    for (int i = 0; i < m; i++) dfsOcean(heights, atlantic, i, n-1, m, n);
    for (int j = 0; j < n; j++) dfsOcean(heights, atlantic, m-1, j, m, n);
    
    List<List<Integer>> result = new ArrayList<>();
    for (int i = 0; i < m; i++)
        for (int j = 0; j < n; j++)
            if (pacific[i][j] && atlantic[i][j])
                result.add(Arrays.asList(i, j));
    return result;
}

private void dfsOcean(int[][] h, boolean[][] visited, int r, int c, int m, int n) {
    visited[r][c] = true;
    for (int[] d : DIRS) {
        int nr = r + d[0], nc = c + d[1];
        if (nr >= 0 && nr < m && nc >= 0 && nc < n 
            && !visited[nr][nc] && h[nr][nc] >= h[r][c]) // flow uphill from ocean
            dfsOcean(h, visited, nr, nc, m, n);
    }
}
```

### Visualization

```
Count Islands:
1 1 0 0 0         Visit from (0,0): sink connected 1s → island #1
1 1 0 0 0         Visit from (0,3) would be 0, skip
0 0 1 0 0         Visit from (2,2): sink → island #2
0 0 0 1 1         Visit from (3,3): sink connected → island #3
                   Answer: 3

Pacific Atlantic:
Pacific ~  ~  ~  ~  ~
     ~  1  2  2  3 (5) ←
     ~  3  2  3 (4)(4) ←
     ~  2  4 (5) 3  1  ←  Atlantic
     ~ (6)(7) 1  4  5  ←
     ~ (5) 1  1  2  4  ←
                ↓  ↓  ↓
Cells in () can reach both oceans
```

### Complexity
- **Time:** O(m * n) — each cell visited at most once per traversal
- **Space:** O(m * n) for recursion stack / visited array

---

## Pattern 5: Grid DP

### Signal
- "Count paths from top-left to bottom-right"
- "Minimum cost path"
- "Largest square/rectangle of 1s"

### Template: Unique Paths

```java
public int uniquePaths(int m, int n) {
    int[] dp = new int[n];
    Arrays.fill(dp, 1); // first row: all 1
    
    for (int i = 1; i < m; i++)
        for (int j = 1; j < n; j++)
            dp[j] += dp[j-1]; // dp[j] = from above + from left
    
    return dp[n-1];
}

// With obstacles:
public int uniquePathsWithObstacles(int[][] grid) {
    int n = grid[0].length;
    int[] dp = new int[n];
    dp[0] = 1;
    
    for (int[] row : grid) {
        for (int j = 0; j < n; j++) {
            if (row[j] == 1) dp[j] = 0;
            else if (j > 0) dp[j] += dp[j-1];
        }
    }
    return dp[n-1];
}
```

### Template: Minimum Path Sum

```java
public int minPathSum(int[][] grid) {
    int m = grid.length, n = grid[0].length;
    int[] dp = new int[n];
    dp[0] = grid[0][0];
    
    // First row
    for (int j = 1; j < n; j++) dp[j] = dp[j-1] + grid[0][j];
    
    // Remaining rows
    for (int i = 1; i < m; i++) {
        dp[0] += grid[i][0];
        for (int j = 1; j < n; j++)
            dp[j] = Math.min(dp[j], dp[j-1]) + grid[i][j];
    }
    return dp[n-1];
}
```

### Template: Maximal Square

```java
public int maximalSquare(char[][] matrix) {
    int m = matrix.length, n = matrix[0].length;
    int[] dp = new int[n + 1]; // dp[j] = side length of largest square ending at (i, j-1)
    int maxSide = 0, prev = 0;
    
    for (int i = 0; i < m; i++) {
        for (int j = 1; j <= n; j++) {
            int temp = dp[j];
            if (matrix[i][j-1] == '1') {
                dp[j] = Math.min(Math.min(dp[j], dp[j-1]), prev) + 1;
                // min(above, left, diagonal) + 1
                maxSide = Math.max(maxSide, dp[j]);
            } else {
                dp[j] = 0;
            }
            prev = temp;
        }
        prev = 0;
    }
    return maxSide * maxSide;
}
```

### Template: Maximal Rectangle (Histogram Approach)

```java
public int maximalRectangle(char[][] matrix) {
    if (matrix.length == 0) return 0;
    int n = matrix[0].length;
    int[] heights = new int[n];
    int maxArea = 0;
    
    for (char[] row : matrix) {
        // Build histogram heights
        for (int j = 0; j < n; j++)
            heights[j] = (row[j] == '1') ? heights[j] + 1 : 0;
        
        // Largest rectangle in histogram (monotonic stack)
        maxArea = Math.max(maxArea, largestRectangleInHistogram(heights));
    }
    return maxArea;
}

private int largestRectangleInHistogram(int[] heights) {
    Deque<Integer> stack = new ArrayDeque<>();
    int max = 0, n = heights.length;
    
    for (int i = 0; i <= n; i++) {
        int h = (i == n) ? 0 : heights[i];
        while (!stack.isEmpty() && h < heights[stack.peek()]) {
            int height = heights[stack.pop()];
            int width = stack.isEmpty() ? i : i - stack.peek() - 1;
            max = Math.max(max, height * width);
        }
        stack.push(i);
    }
    return max;
}
```

### Visualization (Maximal Square)

```
Matrix:          dp (side lengths):
1 0 1 0 0       1 0 1 0 0
1 0 1 1 1       1 0 1 1 1
1 1 1 1 1       1 1 1 2 2
1 0 0 1 0       1 0 0 1 0

dp[i][j] = min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1]) + 1
Max side = 2, area = 4
```

### Visualization (Maximal Rectangle via Histogram)

```
Matrix:          Histogram per row:
1 0 1 0 0       [1,0,1,0,0] → max rect = 1
1 0 1 1 1       [2,0,2,1,1] → max rect = 3
1 1 1 1 1       [3,1,3,2,2] → max rect = 5 ← (full row)
1 0 0 1 0       [4,0,0,3,0] → max rect = 4

Answer: 6 (actually from row 3: heights [3,1,3,2,2] gives 2*3=6)
```

### Complexity
- **Unique Paths:** O(mn) time, O(n) space
- **Min Path Sum:** O(mn) time, O(n) space
- **Maximal Square:** O(mn) time, O(n) space
- **Maximal Rectangle:** O(mn) time, O(n) space

---

## Pattern 6: Set Matrix Zeroes

### Signal
- "If element is 0, set entire row and column to 0"
- "In-place O(1) extra space"

### Template (Java)

```java
public void setZeroes(int[][] matrix) {
    int m = matrix.length, n = matrix[0].length;
    boolean firstRowZero = false, firstColZero = false;
    
    // Check if first row/col should be zeroed
    for (int j = 0; j < n; j++) if (matrix[0][j] == 0) firstRowZero = true;
    for (int i = 0; i < m; i++) if (matrix[i][0] == 0) firstColZero = true;
    
    // Use first row/col as markers
    for (int i = 1; i < m; i++)
        for (int j = 1; j < n; j++)
            if (matrix[i][j] == 0) {
                matrix[i][0] = 0; // mark row
                matrix[0][j] = 0; // mark col
            }
    
    // Zero out cells based on markers
    for (int i = 1; i < m; i++)
        for (int j = 1; j < n; j++)
            if (matrix[i][0] == 0 || matrix[0][j] == 0)
                matrix[i][j] = 0;
    
    // Handle first row and col
    if (firstRowZero) for (int j = 0; j < n; j++) matrix[0][j] = 0;
    if (firstColZero) for (int i = 0; i < m; i++) matrix[i][0] = 0;
}
```

### Visualization

```
Original:         Mark first row/col:     Apply markers:
1  1  1           1  1  1                 1  1  1
1  0  1    →      0  0  1          →      0  0  0
1  1  1           1  1  1                 1  0  1

Key insight: first row & col act as auxiliary arrays IN-PLACE
Separate booleans track whether first row/col themselves need zeroing
```

### Complexity
- **Time:** O(m * n)
- **Space:** O(1) — markers stored in matrix itself

---

## Pattern 7: Game of Life

### Signal
- "Simultaneous cell updates based on neighbor counts"
- "In-place update where all cells read original state"

### Template (Java)

```java
// Encoding: use bits to store [next_state | current_state]
//   0 → was dead, stays dead     (00)
//   1 → was alive, now dead      (01)
//   2 → was dead, now alive      (10)
//   3 → was alive, stays alive   (11)
public void gameOfLife(int[][] board) {
    int m = board.length, n = board[0].length;
    
    for (int i = 0; i < m; i++) {
        for (int j = 0; j < n; j++) {
            int liveNeighbors = countLive(board, i, j, m, n);
            
            if (board[i][j] == 1) { // currently alive
                if (liveNeighbors == 2 || liveNeighbors == 3)
                    board[i][j] = 3; // alive → alive (11)
                // else alive → dead (01, already encoded as 1)
            } else { // currently dead
                if (liveNeighbors == 3)
                    board[i][j] = 2; // dead → alive (10)
            }
        }
    }
    
    // Extract next state (shift right by 1 bit)
    for (int i = 0; i < m; i++)
        for (int j = 0; j < n; j++)
            board[i][j] >>= 1;
}

private int countLive(int[][] board, int r, int c, int m, int n) {
    int count = 0;
    for (int i = r-1; i <= r+1; i++)
        for (int j = c-1; j <= c+1; j++) {
            if (i == r && j == c) continue;
            if (i >= 0 && i < m && j >= 0 && j < n)
                count += (board[i][j] & 1); // read CURRENT state (bit 0)
        }
    return count;
}
```

### Visualization

```
Bit encoding trick:
  Current=1, Next=1 → store 3 (binary 11)
  Current=1, Next=0 → store 1 (binary 01)  ← unchanged!
  Current=0, Next=1 → store 2 (binary 10)
  Current=0, Next=0 → store 0 (binary 00)  ← unchanged!

Read current state: board[i][j] & 1
Final extraction:   board[i][j] >>= 1

This lets us read original state (bit 0) while encoding future state (bit 1)
without any auxiliary storage.
```

### Rules Recap
| Live Neighbors | Alive Cell | Dead Cell |
|:-:|:-:|:-:|
| < 2 | Dies (underpopulation) | Stays dead |
| 2 | Lives | Stays dead |
| 3 | Lives | Becomes alive (reproduction) |
| > 3 | Dies (overpopulation) | Stays dead |

### Complexity
- **Time:** O(m * n)
- **Space:** O(1)

---

## Pattern 8: Diagonal Traversal

### Signal
- "Print matrix diagonally"
- "Zigzag diagonal order"
- "Group elements by i+j"

### Template (Java)

```java
// Zigzag diagonal traversal (LC 498)
public int[] findDiagonalOrder(int[][] mat) {
    int m = mat.length, n = mat[0].length;
    int[] result = new int[m * n];
    int idx = 0;
    
    // There are m + n - 1 diagonals, grouped by i + j = 0, 1, ..., m+n-2
    for (int d = 0; d < m + n - 1; d++) {
        if (d % 2 == 0) {
            // Even diagonal: go UP (row decreases, col increases)
            int r = Math.min(d, m - 1);
            int c = d - r;
            while (r >= 0 && c < n)
                result[idx++] = mat[r--][c++];
        } else {
            // Odd diagonal: go DOWN (row increases, col decreases)
            int c = Math.min(d, n - 1);
            int r = d - c;
            while (c >= 0 && r < m)
                result[idx++] = mat[r++][c--];
        }
    }
    return result;
}
```

### Visualization

```
Matrix:      Diagonals (i+j):     Zigzag output:
1 2 3        d=0: [1]             1
4 5 6        d=1: [4,2]  → ↑2,4  2, 4
7 8 9        d=2: [7,5,3]→ ↑3,5,7  3, 5, 7  (actually down for odd)
             d=3: [8,6]  → ↓6,8    (alternate direction)
             d=4: [9]             9

Even d → traverse up-right: (min(d,m-1), d-r) going r--, c++
Odd d  → traverse down-left: (d-c, min(d,n-1)) going r++, c--
```

### Variant: Collect by Diagonal (No Zigzag)

```java
// Group elements where i + j is the same
List<List<Integer>> diagonals = new ArrayList<>();
for (int d = 0; d < m + n - 1; d++) {
    List<Integer> diag = new ArrayList<>();
    for (int r = Math.max(0, d - n + 1); r <= Math.min(d, m - 1); r++)
        diag.add(mat[r][d - r]);
    diagonals.add(diag);
}
```

### Complexity
- **Time:** O(m * n)
- **Space:** O(1) extra (excluding output)

---

## Pattern 9: Word Search (Grid Backtracking)

### Signal
- "Find if word exists in grid by adjacent cells"
- "Path finding with no revisiting"

### Template (Java)

```java
public boolean exist(char[][] board, String word) {
    int m = board.length, n = board[0].length;
    
    for (int i = 0; i < m; i++)
        for (int j = 0; j < n; j++)
            if (dfs(board, word, i, j, 0, m, n))
                return true;
    return false;
}

private boolean dfs(char[][] board, String word, int r, int c, int idx, int m, int n) {
    if (idx == word.length()) return true;
    if (r < 0 || r >= m || c < 0 || c >= n) return false;
    if (board[r][c] != word.charAt(idx)) return false;
    
    char tmp = board[r][c];
    board[r][c] = '#'; // mark visited (in-place)
    
    boolean found = dfs(board, word, r+1, c, idx+1, m, n)
                 || dfs(board, word, r-1, c, idx+1, m, n)
                 || dfs(board, word, r, c+1, idx+1, m, n)
                 || dfs(board, word, r, c-1, idx+1, m, n);
    
    board[r][c] = tmp; // backtrack (restore)
    return found;
}
```

### Visualization

```
Board:          Word: "ABCCED"
A B C E
S F C S         Path: A(0,0) → B(0,1) → C(0,2) → C(1,2) → E(0,3)? No.
A D E E                                         → E(2,2)? Wait...
                Let me trace: A→B→C→C(1,2)→E(2,2)→D(2,1) ✓

Backtracking: if a path fails, restore '#' → original char, try next direction
```

### Optimization Tips
- **Prune early:** Check character frequency — if word has more of char X than board, return false immediately
- **Start from rarer character:** If last char of word is rarer than first, search reversed word
- **Short-circuit:** Use `||` to stop exploring once found

### Variant: Word Search II (Multiple Words)
- Build a Trie from all words
- DFS through grid, advancing Trie pointer
- Remove found words from Trie (prune branches)

### Complexity
- **Time:** O(m * n * 3^L) where L = word length (3 directions after first since can't revisit)
- **Space:** O(L) recursion depth

---

## Pattern 10: Matrix Exponentiation

### Signal
- "Compute Fibonacci in O(log n)"
- "Linear recurrence with large n"
- "f(n) depends on fixed number of previous terms"

### Core Insight

```
Any linear recurrence: f(n) = a₁·f(n-1) + a₂·f(n-2) + ... + aₖ·f(n-k)
can be expressed as matrix multiplication:

[f(n)  ]   [a₁ a₂ ... aₖ] ^ (n-k)   [f(k)  ]
[f(n-1)] = [1  0  ... 0 ]           × [f(k-1)]
[...   ]   [0  1  ... 0 ]             [...   ]
[f(1)  ]   [0  0  ... 1 0]            [f(1)  ]

Then use fast exponentiation: M^n in O(k³ · log n)
```

### Template: Fibonacci via Matrix Exponentiation

```java
public long fibonacci(int n) {
    if (n <= 1) return n;
    
    long[][] M = {{1, 1},
                  {1, 0}};
    long[][] result = matPow(M, n - 1);
    return result[0][0]; // result[0][0] * F(1) + result[0][1] * F(0) = F(n)
}

private long[][] matPow(long[][] M, int p) {
    int k = M.length;
    long[][] result = new long[k][k];
    // Initialize as identity matrix
    for (int i = 0; i < k; i++) result[i][i] = 1;
    
    while (p > 0) {
        if ((p & 1) == 1)
            result = matMul(result, M);
        M = matMul(M, M);
        p >>= 1;
    }
    return result;
}

private long[][] matMul(long[][] A, long[][] B) {
    int k = A.length;
    long[][] C = new long[k][k];
    for (int i = 0; i < k; i++)
        for (int j = 0; j < k; j++)
            for (int x = 0; x < k; x++)
                C[i][j] += A[i][x] * B[x][j];
    return C;
}
```

### Template: With Modular Arithmetic

```java
private static final long MOD = 1_000_000_007;

private long[][] matMulMod(long[][] A, long[][] B) {
    int k = A.length;
    long[][] C = new long[k][k];
    for (int i = 0; i < k; i++)
        for (int j = 0; j < k; j++)
            for (int x = 0; x < k; x++)
                C[i][j] = (C[i][j] + A[i][x] * B[x][j]) % MOD;
    return C;
}
```

### Visualization

```
Fibonacci recurrence: F(n) = F(n-1) + F(n-2)

Matrix form:
[F(n)  ]   [1 1]^(n-1)   [F(1)]   [1 1]^(n-1)   [1]
[F(n-1)] = [1 0]        × [F(0)] = [1 0]        × [0]

Example: F(6) = 8
[1 1]^5 = [8 5]     →  result[0][0] = 8 = F(6)
[1 0]     [5 3]

Exponentiation by squaring:
M^13 = M^8 × M^4 × M^1    (13 = 1101 in binary)
Only log₂(n) multiplications needed!
```

### Common Recurrences as Matrices

| Problem | Recurrence | Matrix |
|---------|-----------|--------|
| Fibonacci | f(n) = f(n-1) + f(n-2) | `[[1,1],[1,0]]` |
| Tribonacci | f(n) = f(n-1)+f(n-2)+f(n-3) | `[[1,1,1],[1,0,0],[0,1,0]]` |
| Stair climbing (1,2,3 steps) | Same as Tribonacci | Same |
| Number of paths of length n in graph | Adjacency matrix A | A^n |

### Complexity
- **Time:** O(k³ · log n) where k = matrix dimension (recurrence order)
- **Space:** O(k²)
- For Fibonacci: O(8 · log n) = O(log n) vs naive O(n)

---

## Quick Reference: When to Use What

| Problem Type | Pattern | Key Technique |
|:--|:--|:--|
| Traverse in spiral/diagonal order | 1, 8 | Boundary pointers, i+j grouping |
| Transform geometry | 2 | Transpose + Reverse |
| Find element | 3 | Binary search or staircase |
| Connected regions | 4 | DFS/BFS flood fill |
| Optimal path/count | 5 | DP with 1D rolling array |
| Propagate constraints | 6 | Use matrix as its own marker |
| Simultaneous state change | 7 | Bit encoding for old+new state |
| Exists path with backtrack | 9 | DFS + restore visited |
| Large-n recurrence | 10 | Matrix fast exponentiation |

---

## Common Pitfalls

1. **Off-by-one in spiral**: Forgetting `if (top <= bottom)` / `if (left <= right)` checks causes duplicate traversal in single-row/col cases
2. **Mutation during iteration**: Island counting mutates grid — clone first if original needed
3. **Grid DP boundary**: Initialize first row AND first column separately before filling interior
4. **Staircase search direction**: Starting from wrong corner (e.g., top-left) gives O(mn) not O(m+n)
5. **Matrix exponentiation overflow**: Always apply modulo inside multiplication loop, not after
6. **Word search revisiting**: Must restore cell after backtracking — common bug is forgetting to un-mark
7. **Game of Life read order**: Must read `& 1` (original bit), not the modified value
