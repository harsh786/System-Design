import java.util.*;

/**
 * Problem: Number of Distinct Islands (LeetCode 694)
 * Approach: DFS recording path signature (directions) to identify shape; use Set for uniqueness
 * Time: O(M*N), Space: O(M*N)
 * Production Analogy: Deduplicating topology patterns across multiple deployments
 */
public class Problem47_NumberOfDistinctIslands {
    public int numDistinctIslands(int[][] grid) {
        Set<String> shapes = new HashSet<>();
        for (int i = 0; i < grid.length; i++)
            for (int j = 0; j < grid[0].length; j++)
                if (grid[i][j] == 1) {
                    StringBuilder sb = new StringBuilder();
                    dfs(grid, i, j, sb, 'S');
                    shapes.add(sb.toString());
                }
        return shapes.size();
    }

    private void dfs(int[][] grid, int i, int j, StringBuilder sb, char dir) {
        if (i < 0 || i >= grid.length || j < 0 || j >= grid[0].length || grid[i][j] == 0) return;
        grid[i][j] = 0;
        sb.append(dir);
        dfs(grid, i+1, j, sb, 'D'); dfs(grid, i-1, j, sb, 'U');
        dfs(grid, i, j+1, sb, 'R'); dfs(grid, i, j-1, sb, 'L');
        sb.append('B'); // backtrack marker
    }

    public static void main(String[] args) {
        int[][] grid = {{1,1,0,0,0},{1,0,0,0,0},{0,0,0,1,1},{0,0,0,0,1}};
        System.out.println(new Problem47_NumberOfDistinctIslands().numDistinctIslands(grid)); // 2? depends on shape
    }
}
