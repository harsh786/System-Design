import java.util.*;

/**
 * Problem 24: Unique Paths III (LeetCode 980)
 * 
 * Find number of paths from start to end visiting every non-obstacle cell exactly once.
 * 
 * Search Tree:
 * - DFS from start, try 4 directions, mark visited
 * - Count path only if all empty cells visited when reaching end
 * 
 * Pruning Strategy:
 * - Track count of empty cells; only count path when all visited
 * - Don't revisit cells (mark visited)
 * 
 * Time Complexity: O(3^(m*n)) worst case but grid is small (max 20 cells)
 * Space Complexity: O(m*n)
 * 
 * Production Analogy:
 * - Complete coverage routing: robot/drone path planning that must visit every accessible point.
 */
public class Problem24_UniquePathsIII {

    private int result;
    private int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};

    public int uniquePathsIII(int[][] grid) {
        result = 0;
        int m = grid.length, n = grid[0].length;
        int startR = 0, startC = 0, empty = 0;
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                if (grid[i][j] == 1) { startR = i; startC = j; }
                if (grid[i][j] != -1) empty++;
            }
        dfs(grid, startR, startC, empty);
        return result;
    }

    private void dfs(int[][] grid, int r, int c, int remaining) {
        if (r < 0 || r >= grid.length || c < 0 || c >= grid[0].length || grid[r][c] == -1) return;
        if (grid[r][c] == 2) {
            if (remaining == 1) result++;
            return;
        }
        grid[r][c] = -1; // mark visited
        for (int[] d : dirs) dfs(grid, r + d[0], c + d[1], remaining - 1);
        grid[r][c] = 0; // restore
    }

    public static void main(String[] args) {
        Problem24_UniquePathsIII sol = new Problem24_UniquePathsIII();

        System.out.println(sol.uniquePathsIII(new int[][]{{1,0,0,0},{0,0,0,0},{0,0,2,-1}})); // 2
        System.out.println(sol.uniquePathsIII(new int[][]{{1,0,0,0},{0,0,0,0},{0,0,0,2}})); // 4
        System.out.println(sol.uniquePathsIII(new int[][]{{0,1},{2,0}})); // 0
    }
}
