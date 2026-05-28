import java.util.*;

/**
 * Problem: Pacific Atlantic Water Flow (LeetCode 417)
 * Approach: DFS from ocean borders inward - find intersection of cells reachable from both oceans
 * Time: O(M*N), Space: O(M*N)
 * Production Analogy: Bi-directional reachability analysis in network routing
 */
public class Problem05_PacificAtlanticWaterFlow {
    int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};

    public List<List<Integer>> pacificAtlantic(int[][] heights) {
        int m = heights.length, n = heights[0].length;
        boolean[][] pacific = new boolean[m][n], atlantic = new boolean[m][n];
        for (int i = 0; i < m; i++) { dfs(heights, pacific, i, 0); dfs(heights, atlantic, i, n-1); }
        for (int j = 0; j < n; j++) { dfs(heights, pacific, 0, j); dfs(heights, atlantic, m-1, j); }
        List<List<Integer>> res = new ArrayList<>();
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                if (pacific[i][j] && atlantic[i][j]) res.add(Arrays.asList(i, j));
        return res;
    }

    private void dfs(int[][] heights, boolean[][] visited, int i, int j) {
        visited[i][j] = true;
        for (int[] d : dirs) {
            int ni = i + d[0], nj = j + d[1];
            if (ni >= 0 && ni < heights.length && nj >= 0 && nj < heights[0].length
                && !visited[ni][nj] && heights[ni][nj] >= heights[i][j])
                dfs(heights, visited, ni, nj);
        }
    }

    public static void main(String[] args) {
        Problem05_PacificAtlanticWaterFlow sol = new Problem05_PacificAtlanticWaterFlow();
        int[][] h = {{1,2,2,3,5},{3,2,3,4,4},{2,4,5,3,1},{6,7,1,4,5},{5,1,1,2,4}};
        System.out.println(sol.pacificAtlantic(h));
    }
}
