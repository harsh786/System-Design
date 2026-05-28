/**
 * Problem: Closed Island (LeetCode 1254)
 * Approach: DFS - an island is closed if it doesn't touch any border
 * Time: O(M*N), Space: O(M*N)
 * Production Analogy: Identifying fully encapsulated internal services with no external exposure
 */
public class Problem34_ClosedIsland {
    public int closedIsland(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        // Eliminate border-connected land (0 = land, 1 = water)
        for (int i = 0; i < m; i++) { fill(grid, i, 0); fill(grid, i, n-1); }
        for (int j = 0; j < n; j++) { fill(grid, 0, j); fill(grid, m-1, j); }
        int count = 0;
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                if (grid[i][j] == 0) { fill(grid, i, j); count++; }
        return count;
    }

    private void fill(int[][] grid, int i, int j) {
        if (i < 0 || i >= grid.length || j < 0 || j >= grid[0].length || grid[i][j] != 0) return;
        grid[i][j] = 1;
        fill(grid, i+1, j); fill(grid, i-1, j); fill(grid, i, j+1); fill(grid, i, j-1);
    }

    public static void main(String[] args) {
        int[][] grid = {{1,1,1,1,1,1,1,0},{1,0,0,0,0,1,1,0},{1,0,1,0,1,1,1,0},{1,0,0,0,0,1,0,1},{1,1,1,1,1,1,1,0}};
        System.out.println(new Problem34_ClosedIsland().closedIsland(grid)); // 2
    }
}
