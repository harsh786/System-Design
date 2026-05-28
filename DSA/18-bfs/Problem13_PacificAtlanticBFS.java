import java.util.*;

/**
 * Problem: Pacific Atlantic Water Flow BFS (LeetCode 417)
 * Approach: Multi-source BFS from each ocean border, find intersection
 * Time: O(M*N), Space: O(M*N)
 * Production Analogy: Bidirectional reachability analysis for network routing optimization
 */
public class Problem13_PacificAtlanticBFS {
    int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};

    public List<List<Integer>> pacificAtlantic(int[][] heights) {
        int m = heights.length, n = heights[0].length;
        boolean[][] pacific = new boolean[m][n], atlantic = new boolean[m][n];
        Queue<int[]> pq = new LinkedList<>(), aq = new LinkedList<>();
        for (int i = 0; i < m; i++) { pq.offer(new int[]{i,0}); pacific[i][0]=true; aq.offer(new int[]{i,n-1}); atlantic[i][n-1]=true; }
        for (int j = 0; j < n; j++) { pq.offer(new int[]{0,j}); pacific[0][j]=true; aq.offer(new int[]{m-1,j}); atlantic[m-1][j]=true; }
        bfs(heights, pq, pacific);
        bfs(heights, aq, atlantic);
        List<List<Integer>> res = new ArrayList<>();
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                if (pacific[i][j] && atlantic[i][j]) res.add(Arrays.asList(i, j));
        return res;
    }

    private void bfs(int[][] heights, Queue<int[]> q, boolean[][] visited) {
        while (!q.isEmpty()) {
            int[] cell = q.poll();
            for (int[] d : dirs) {
                int ni = cell[0]+d[0], nj = cell[1]+d[1];
                if (ni >= 0 && ni < heights.length && nj >= 0 && nj < heights[0].length
                    && !visited[ni][nj] && heights[ni][nj] >= heights[cell[0]][cell[1]]) {
                    visited[ni][nj] = true; q.offer(new int[]{ni, nj});
                }
            }
        }
    }

    public static void main(String[] args) {
        int[][] h = {{1,2,2,3,5},{3,2,3,4,4},{2,4,5,3,1},{6,7,1,4,5},{5,1,1,2,4}};
        System.out.println(new Problem13_PacificAtlanticBFS().pacificAtlantic(h));
    }
}
