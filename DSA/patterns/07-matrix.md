# Matrix - Pattern Guide

---

## Pattern Recognition Signals

| Signal | Pattern |
|--------|---------|
| Read/write in spiral order | Boundary shrinking |
| Rotate matrix 90° | Transpose + Reverse |
| Search in sorted matrix | Staircase / Binary Search |
| Count islands / connected regions | DFS/BFS Flood Fill |
| Count paths / min cost in grid | Grid DP |
| Simultaneous cell updates | In-place state encoding |
| Diagonal processing | (i+j) grouping |
| Set rows/cols to zero | First row/col as markers |
| Largest rectangle of 1s | Histogram per row |

---

## Pattern 1: Spiral Traversal

**When:** Read or write matrix in spiral (clockwise) order.

### Template
```java
int top = 0, bottom = m-1, left = 0, right = n-1;
List<Integer> result = new ArrayList<>();

while (top <= bottom && left <= right) {
    // → Right along top row
    for (int i = left; i <= right; i++) result.add(matrix[top][i]);
    top++;
    
    // ↓ Down along right column
    for (int i = top; i <= bottom; i++) result.add(matrix[i][right]);
    right--;
    
    // ← Left along bottom row (if still valid)
    if (top <= bottom)
        for (int i = right; i >= left; i--) result.add(matrix[bottom][i]);
    bottom--;
    
    // ↑ Up along left column (if still valid)
    if (left <= right)
        for (int i = bottom; i >= top; i--) result.add(matrix[i][left]);
    left++;
}
```

### Visualization
```
[1,  2,  3,  4]       Traversal order:
[5,  6,  7,  8]       → 1,2,3,4
[9, 10, 11, 12]       ↓ 8,12
[13,14, 15, 16]       ← 16,15,14,13
                       ↑ 9,5
                       → 6,7
                       ↓ 11
                       ← 10

Layer by layer: outer ring → inner ring → ...
```

### Generate Spiral Matrix (Fill)
```java
int[][] matrix = new int[n][n];
int num = 1;
// Same boundary approach, but matrix[row][col] = num++ instead of reading
```

**Complexity:** O(m*n) time, O(1) extra space

---

## Pattern 2: Rotate Matrix 90° (Transpose + Reverse)

**When:** Rotate square matrix in-place.

### Template
```java
// CLOCKWISE 90°:
// Step 1: Transpose (swap across diagonal)
for (int i = 0; i < n; i++)
    for (int j = i + 1; j < n; j++)
        swap(matrix[i][j], matrix[j][i]);

// Step 2: Reverse each row
for (int[] row : matrix)
    reverse(row);
```

### All Rotations
```
Clockwise 90°:       Transpose → Reverse rows
Counter-clockwise:   Transpose → Reverse columns
                     OR: Reverse rows → Transpose
180°:                Reverse rows → Reverse each row
Flip horizontal:     Reverse each row
Flip vertical:       Reverse row order
```

### Visualization
```
Original:    Transpose:    Reverse rows:
[1, 2, 3]   [1, 4, 7]    [7, 4, 1]
[4, 5, 6] → [2, 5, 8] →  [8, 5, 2]   = 90° clockwise ✓
[7, 8, 9]   [3, 6, 9]    [9, 6, 3]
```

**Complexity:** O(n²) time, O(1) space

---

## Pattern 3: Search in Sorted Matrix

### Case A: Row-major Sorted (each row starts where previous ends)
```java
// Treat as 1D sorted array → binary search
int lo = 0, hi = m * n - 1;
while (lo <= hi) {
    int mid = (lo + hi) / 2;
    int val = matrix[mid / n][mid % n];  // convert 1D index to 2D
    if (val == target) return true;
    else if (val < target) lo = mid + 1;
    else hi = mid - 1;
}
// O(log(m*n))
```

### Case B: Rows and Columns Each Sorted (not globally)
```java
// Staircase search: start from top-right (or bottom-left)
int row = 0, col = n - 1;
while (row < m && col >= 0) {
    if (matrix[row][col] == target) return true;
    else if (matrix[row][col] > target) col--;   // too big → go left
    else row++;                                    // too small → go down
}
return false;
// O(m + n)
```

### Visualization (Staircase)
```
[1,  4,  7, 11]
[2,  5,  8, 12]    Target = 5
[3,  6,  9, 16]    
[10,13, 14, 17]

Start at 11 (top-right):
  11 > 5 → go left (col--)
  7 > 5 → go left
  4 < 5 → go down (row++)
  5 == 5 → FOUND! ✓
```

---

## Pattern 4: Island Problems (DFS/BFS Flood Fill)

**When:** Count islands, max area, perimeter, distinct shapes.

### Template: Count Islands
```java
int count = 0;
for (int i = 0; i < m; i++) {
    for (int j = 0; j < n; j++) {
        if (grid[i][j] == '1') {
            count++;
            dfs(grid, i, j);  // mark entire island visited
        }
    }
}

void dfs(char[][] grid, int i, int j) {
    if (i < 0 || i >= m || j < 0 || j >= n || grid[i][j] != '1') return;
    grid[i][j] = '0';  // mark visited (or use separate visited array)
    dfs(grid, i+1, j); dfs(grid, i-1, j);
    dfs(grid, i, j+1); dfs(grid, i, j-1);
}
```

### Variants

| Problem | Modification |
|---------|-------------|
| Max Area of Island | DFS returns size (count cells) |
| Island Perimeter | Count edges touching water/boundary |
| Surrounded Regions | BFS from borders first → mark safe 'O's |
| Distinct Island Shapes | Normalize path string (DFS direction sequence) |
| Number of Islands II (online) | Union-Find with dynamic cell activation |
| Pacific Atlantic Water Flow | BFS inward from each ocean boundary |

### Surrounded Regions Strategy
```
O O O O        O O O O
O X O O   →    O X O O    Only interior O's get flipped
O O X O        O O X O    Border-connected O's stay
O O O O        O O O O

Algorithm:
1. BFS/DFS from all border 'O' → mark as safe ('S')
2. Remaining 'O' → flip to 'X'
3. 'S' → restore to 'O'
```

---

## Pattern 5: Grid DP

**When:** Count paths, minimum cost paths, maximal square/rectangle.

### Unique Paths
```java
int[][] dp = new int[m][n];
Arrays.fill(dp[0], 1);                    // top row: one way
for (int i = 0; i < m; i++) dp[i][0] = 1; // left col: one way
for (int i = 1; i < m; i++)
    for (int j = 1; j < n; j++)
        dp[i][j] = dp[i-1][j] + dp[i][j-1];  // from above + from left
```

### Minimum Path Sum
```java
for (int i = 0; i < m; i++)
    for (int j = 0; j < n; j++) {
        if (i == 0 && j == 0) dp[i][j] = grid[i][j];
        else if (i == 0) dp[i][j] = dp[i][j-1] + grid[i][j];
        else if (j == 0) dp[i][j] = dp[i-1][j] + grid[i][j];
        else dp[i][j] = Math.min(dp[i-1][j], dp[i][j-1]) + grid[i][j];
    }
```

### Maximal Square
```java
// dp[i][j] = side length of largest square with bottom-right corner at (i,j)
for (int i = 1; i < m; i++)
    for (int j = 1; j < n; j++)
        if (matrix[i][j] == '1')
            dp[i][j] = Math.min(dp[i-1][j], Math.min(dp[i][j-1], dp[i-1][j-1])) + 1;
// Answer = max(dp[i][j])²
```

### Visualization: Maximal Square
```
Matrix:          DP:
1 0 1 0 0       1 0 1 0 0
1 0 1 1 1       1 0 1 1 1
1 1 1 1 1   →   1 1 1 2 2
1 0 0 1 0       1 0 0 1 0

dp[2][3] = min(dp[1][3], dp[2][2], dp[1][2]) + 1 = min(1,1,1) + 1 = 2
Largest square has side 2, area 4.
```

### Maximal Rectangle (Histogram per row)
```java
int[] heights = new int[n];
int maxArea = 0;
for (int i = 0; i < m; i++) {
    for (int j = 0; j < n; j++) {
        heights[j] = (matrix[i][j] == '1') ? heights[j] + 1 : 0;
    }
    maxArea = Math.max(maxArea, largestRectangleInHistogram(heights));
}
```

---

## Pattern 6: Set Matrix Zeroes (In-Place Marking)

**When:** Set entire row/col to zero if any cell is zero. O(1) space.

### Template
```java
boolean firstRowZero = false, firstColZero = false;

// Check if first row/col need zeroing
for (int j = 0; j < n; j++) if (matrix[0][j] == 0) firstRowZero = true;
for (int i = 0; i < m; i++) if (matrix[i][0] == 0) firstColZero = true;

// Use first row/col as markers
for (int i = 1; i < m; i++)
    for (int j = 1; j < n; j++)
        if (matrix[i][j] == 0) {
            matrix[i][0] = 0;  // mark row
            matrix[0][j] = 0;  // mark col
        }

// Zero based on markers
for (int i = 1; i < m; i++)
    for (int j = 1; j < n; j++)
        if (matrix[i][0] == 0 || matrix[0][j] == 0)
            matrix[i][j] = 0;

// Handle first row/col last
if (firstRowZero) Arrays.fill(matrix[0], 0);
if (firstColZero) for (int i = 0; i < m; i++) matrix[i][0] = 0;
```

---

## Pattern 7: Game of Life (Simultaneous State Update)

**When:** All cells update simultaneously based on current neighbors.

### In-Place Encoding
```java
// Encode transitions in bits:
// bit 0 = current state, bit 1 = next state
// 0→0: 0, 1→0: 1, 0→1: 2, 1→1: 3

for (int i = 0; i < m; i++)
    for (int j = 0; j < n; j++) {
        int liveNeighbors = countLive(board, i, j);  // use (cell & 1) for current
        if (board[i][j] == 1) {
            if (liveNeighbors == 2 || liveNeighbors == 3)
                board[i][j] = 3;  // 1→1 (lives)
            // else stays 1 (bit 0 = current=1, bit 1 = next=0)
        } else {
            if (liveNeighbors == 3)
                board[i][j] = 2;  // 0→1 (born)
        }
    }

// Extract next state
for (int i = 0; i < m; i++)
    for (int j = 0; j < n; j++)
        board[i][j] >>= 1;  // shift to get next state
```

---

## Pattern 8: Diagonal Traversal

**When:** Process matrix diagonally.

### Key Insight
```
Same diagonal: i + j is constant
Same anti-diagonal: i - j is constant

For zigzag diagonal traversal:
  Even diagonals (i+j is even): go UP (row--, col++)
  Odd diagonals (i+j is odd):  go DOWN (row++, col--)
```

### Template
```java
List<Integer> result = new ArrayList<>();
for (int d = 0; d < m + n - 1; d++) {
    if (d % 2 == 0) {  // upward
        int r = Math.min(d, m - 1), c = d - r;
        while (r >= 0 && c < n) result.add(matrix[r--][c++]);
    } else {  // downward
        int c = Math.min(d, n - 1), r = d - c;
        while (c >= 0 && r < m) result.add(matrix[r++][c--]);
    }
}
```

---

## Pattern 9: Word Search (Grid Backtracking)

```java
boolean dfs(char[][] board, String word, int i, int j, int idx) {
    if (idx == word.length()) return true;
    if (i < 0 || i >= m || j < 0 || j >= n) return false;
    if (board[i][j] != word.charAt(idx)) return false;
    
    char temp = board[i][j];
    board[i][j] = '#';  // mark visited
    
    boolean found = dfs(board, word, i+1, j, idx+1) ||
                    dfs(board, word, i-1, j, idx+1) ||
                    dfs(board, word, i, j+1, idx+1) ||
                    dfs(board, word, i, j-1, idx+1);
    
    board[i][j] = temp;  // unmark (backtrack)
    return found;
}
```

---

## Summary Flowchart

```
Matrix Problem?
│
├─ Spiral order? ───────────────→ 4-boundary shrinking
│
├─ Rotate? ─────────────────────→ Transpose + Reverse
│
├─ Search sorted? ──────────────→ Staircase (O(m+n)) or Binary (O(log(mn)))
│
├─ Count/area of connected? ────→ DFS/BFS Flood Fill
│
├─ Count paths / min cost? ─────→ Grid DP
│
├─ Largest rectangle/square? ──→ DP (histogram per row for rectangle)
│
├─ Zero entire row/col? ────────→ First row/col as markers
│
├─ Simultaneous update? ────────→ Bit-encoded state transitions
│
├─ Diagonal processing? ────────→ Group by (i+j)
│
└─ Find word in grid? ──────────→ DFS backtracking
```
