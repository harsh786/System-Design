import java.util.*;

/**
 * Problem 5: Pacific Atlantic Water Flow (LeetCode 417)
 * 
 * Approach: BFS from ocean borders inward. A cell reachable from both oceans is in the answer.
 * Time: O(M*N), Space: O(M*N)
 * 
 * Production Analogy: Data replication - finding nodes that can sync to both primary and DR regions.
 */
public class Problem05_PacificAtlanticWaterFlow {
    
    public List<List<Integer>> pacificAtlantic(int[][] heights) {
        int m = heights.length, n = heights[0].length;
        boolean[][] pacific = new boolean[m][n], atlantic = new boolean[m][n];
        Queue<int[]> pq = new LinkedList<>(), aq = new LinkedList<>();
        for (int i = 0; i < m; i++) { pq.offer(new int[]{i,0}); pacific[i][0]=true; aq.offer(new int[]{i,n-1}); atlantic[i][n-1]=true; }
        for (int j = 0; j < n; j++) { pq.offer(new int[]{0,j}); pacific[0][j]=true; aq.offer(new int[]{m-1,j}); atlantic[m-1][j]=true; }
        bfs(heights, pq, pacific, m, n);
        bfs(heights, aq, atlantic, m, n);
        List<List<Integer>> res = new ArrayList<>();
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                if (pacific[i][j] && atlantic[i][j]) res.add(Arrays.asList(i, j));
        return res;
    }
    
    private void bfs(int[][] h, Queue<int[]> q, boolean[][] visited, int m, int n) {
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!q.isEmpty()) {
            int[] c = q.poll();
            for (int[] d : dirs) {
                int ni = c[0]+d[0], nj = c[1]+d[1];
                if (ni>=0 && ni<m && nj>=0 && nj<n && !visited[ni][nj] && h[ni][nj] >= h[c[0]][c[1]]) {
                    visited[ni][nj] = true;
                    q.offer(new int[]{ni, nj});
                }
            }
        }
    }
    
    public static void main(String[] args) {
        Problem05_PacificAtlanticWaterFlow sol = new Problem05_PacificAtlanticWaterFlow();
        int[][] h = {{1,2,2,3,5},{3,2,3,4,4},{2,4,5,3,1},{6,7,1,4,5},{5,1,1,2,4}};
        System.out.println(sol.pacificAtlantic(h));
        int[][] h2 = {{1}};
        System.out.println(sol.pacificAtlantic(h2)); // [[0,0]]
    }
}
