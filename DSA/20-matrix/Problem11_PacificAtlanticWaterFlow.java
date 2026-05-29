import java.util.*;

/**
 * Problem 11: Pacific Atlantic Water Flow
 * 
 * Find cells where water can flow to both Pacific and Atlantic oceans.
 *
 * Approach: Reverse BFS/DFS from ocean borders inward. Find intersection of cells
 * reachable from Pacific border and Atlantic border.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(m * n)
 *
 * Production Analogy: Network reachability analysis - finding nodes that can reach
 * both data centers. Or in CDN routing, finding locations served by multiple edge regions.
 */
public class Problem11_PacificAtlanticWaterFlow {

    public static List<List<Integer>> pacificAtlantic(int[][] heights) {
        int m = heights.length, n = heights[0].length;
        boolean[][] pacific = new boolean[m][n], atlantic = new boolean[m][n];

        for (int i = 0; i < m; i++) { dfs(heights, pacific, i, 0); dfs(heights, atlantic, i, n-1); }
        for (int j = 0; j < n; j++) { dfs(heights, pacific, 0, j); dfs(heights, atlantic, m-1, j); }

        List<List<Integer>> result = new ArrayList<>();
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                if (pacific[i][j] && atlantic[i][j])
                    result.add(Arrays.asList(i, j));
        return result;
    }

    private static void dfs(int[][] heights, boolean[][] visited, int i, int j) {
        visited[i][j] = true;
        int[] dx = {0,0,1,-1}, dy = {1,-1,0,0};
        for (int d = 0; d < 4; d++) {
            int ni = i + dx[d], nj = j + dy[d];
            if (ni >= 0 && ni < heights.length && nj >= 0 && nj < heights[0].length
                && !visited[ni][nj] && heights[ni][nj] >= heights[i][j])
                dfs(heights, visited, ni, nj);
        }
    }

    public static void main(String[] args) {
        int[][] h = {{1,2,2,3,5},{3,2,3,4,4},{2,4,5,3,1},{6,7,1,4,5},{5,1,1,2,4}};
        System.out.println("Test 1: " + pacificAtlantic(h));

        int[][] h2 = {{1}};
        System.out.println("Test 2: " + pacificAtlantic(h2)); // [[0,0]]
    }
}
