/**
 * Problem: Number of Enclaves (LeetCode 1020)
 * Approach: DFS from borders to eliminate escapable land, count remaining
 * Time: O(M*N), Space: O(M*N)
 * Production Analogy: Counting internal-only data that cannot leak to external boundaries
 */
public class Problem35_NumberOfEnclaves {
    public int numEnclaves(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        for (int i = 0; i < m; i++) { sink(grid, i, 0); sink(grid, i, n-1); }
        for (int j = 0; j < n; j++) { sink(grid, 0, j); sink(grid, m-1, j); }
        int count = 0;
        for (int[] row : grid) for (int cell : row) count += cell;
        return count;
    }

    private void sink(int[][] grid, int i, int j) {
        if (i < 0 || i >= grid.length || j < 0 || j >= grid[0].length || grid[i][j] == 0) return;
        grid[i][j] = 0;
        sink(grid, i+1, j); sink(grid, i-1, j); sink(grid, i, j+1); sink(grid, i, j-1);
    }

    public static void main(String[] args) {
        int[][] grid = {{0,0,0,0},{1,0,1,0},{0,1,1,0},{0,0,0,0}};
        System.out.println(new Problem35_NumberOfEnclaves().numEnclaves(grid)); // 3
    }
}
