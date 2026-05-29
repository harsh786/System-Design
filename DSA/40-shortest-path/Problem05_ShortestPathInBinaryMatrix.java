import java.util.*;

/**
 * Problem: Shortest Path in Binary Matrix
 * Find shortest path from (0,0) to (n-1,n-1) in binary grid (8-directional).
 *
 * Approach: BFS on unweighted graph
 *
 * Time Complexity: O(n^2)
 * Space Complexity: O(n^2)
 *
 * Production Analogy: Finding minimum hops in a network with blocked nodes.
 */
public class Problem05_ShortestPathInBinaryMatrix {

    public int shortestPathBinaryMatrix(int[][] grid) {
        int n = grid.length;
        if (grid[0][0] != 0 || grid[n-1][n-1] != 0) return -1;

        Queue<int[]> q = new LinkedList<>();
        q.offer(new int[]{0, 0, 1});
        grid[0][0] = 1;

        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0},{1,1},{1,-1},{-1,1},{-1,-1}};
        while (!q.isEmpty()) {
            int[] cur = q.poll();
            if (cur[0] == n-1 && cur[1] == n-1) return cur[2];
            for (int[] d : dirs) {
                int nr = cur[0]+d[0], nc = cur[1]+d[1];
                if (nr>=0 && nr<n && nc>=0 && nc<n && grid[nr][nc] == 0) {
                    grid[nr][nc] = 1;
                    q.offer(new int[]{nr, nc, cur[2]+1});
                }
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        Problem05_ShortestPathInBinaryMatrix solver = new Problem05_ShortestPathInBinaryMatrix();
        System.out.println(solver.shortestPathBinaryMatrix(new int[][]{{0,1},{1,0}})); // 2
    }
}
