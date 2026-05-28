import java.util.*;

/**
 * Problem: Shortest Path in Binary Matrix (LeetCode 1091)
 * Approach: BFS 8-directional from top-left to bottom-right
 * Time: O(N^2), Space: O(N^2)
 * Production Analogy: Finding shortest network path with 8-way connectivity
 */
public class Problem05_ShortestPathBinaryMatrix {
    public int shortestPathBinaryMatrix(int[][] grid) {
        int n = grid.length;
        if (grid[0][0] == 1 || grid[n-1][n-1] == 1) return -1;
        int[][] dirs = {{-1,-1},{-1,0},{-1,1},{0,-1},{0,1},{1,-1},{1,0},{1,1}};
        Queue<int[]> q = new LinkedList<>();
        q.offer(new int[]{0,0});
        grid[0][0] = 1;
        int dist = 1;
        while (!q.isEmpty()) {
            int size = q.size();
            for (int i = 0; i < size; i++) {
                int[] cell = q.poll();
                if (cell[0] == n-1 && cell[1] == n-1) return dist;
                for (int[] d : dirs) {
                    int ni = cell[0]+d[0], nj = cell[1]+d[1];
                    if (ni >= 0 && ni < n && nj >= 0 && nj < n && grid[ni][nj] == 0) {
                        grid[ni][nj] = 1; q.offer(new int[]{ni, nj});
                    }
                }
            }
            dist++;
        }
        return -1;
    }

    public static void main(String[] args) {
        int[][] grid = {{0,0,0},{1,1,0},{1,1,0}};
        System.out.println(new Problem05_ShortestPathBinaryMatrix().shortestPathBinaryMatrix(grid)); // 4
    }
}
