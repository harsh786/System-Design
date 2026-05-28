import java.util.*;

/**
 * Problem: Number of Islands BFS (LeetCode 200)
 * Approach: BFS flood fill from each unvisited land cell
 * Time: O(M*N), Space: O(min(M,N))
 * Production Analogy: Iterative cluster discovery using breadth-first scanning
 */
public class Problem07_NumberOfIslandsBFS {
    public int numIslands(char[][] grid) {
        int m = grid.length, n = grid[0].length, count = 0;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                if (grid[i][j] == '1') {
                    count++;
                    Queue<int[]> q = new LinkedList<>();
                    q.offer(new int[]{i,j}); grid[i][j] = '0';
                    while (!q.isEmpty()) {
                        int[] cell = q.poll();
                        for (int[] d : dirs) {
                            int ni = cell[0]+d[0], nj = cell[1]+d[1];
                            if (ni >= 0 && ni < m && nj >= 0 && nj < n && grid[ni][nj] == '1') {
                                grid[ni][nj] = '0'; q.offer(new int[]{ni, nj});
                            }
                        }
                    }
                }
        return count;
    }

    public static void main(String[] args) {
        char[][] grid = {{'1','1','0','0'},{'1','1','0','0'},{'0','0','1','0'},{'0','0','0','1'}};
        System.out.println(new Problem07_NumberOfIslandsBFS().numIslands(grid)); // 3
    }
}
