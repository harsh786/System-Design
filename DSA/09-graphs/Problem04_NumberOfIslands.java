import java.util.*;

/**
 * Problem 4: Number of Islands (LeetCode 200)
 * 
 * Approach: BFS/DFS flood fill. For each unvisited '1', start BFS and mark all connected land.
 * Time: O(M*N), Space: O(M*N)
 * 
 * Production Analogy: Identifying independent clusters in a distributed system topology map.
 */
public class Problem04_NumberOfIslands {
    
    public int numIslands(char[][] grid) {
        if (grid == null || grid.length == 0) return 0;
        int m = grid.length, n = grid[0].length, count = 0;
        for (int i = 0; i < m; i++) {
            for (int j = 0; j < n; j++) {
                if (grid[i][j] == '1') {
                    count++;
                    bfs(grid, i, j, m, n);
                }
            }
        }
        return count;
    }
    
    private void bfs(char[][] grid, int i, int j, int m, int n) {
        Queue<int[]> q = new LinkedList<>();
        q.offer(new int[]{i, j});
        grid[i][j] = '0';
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!q.isEmpty()) {
            int[] cell = q.poll();
            for (int[] d : dirs) {
                int ni = cell[0]+d[0], nj = cell[1]+d[1];
                if (ni >= 0 && ni < m && nj >= 0 && nj < n && grid[ni][nj] == '1') {
                    grid[ni][nj] = '0';
                    q.offer(new int[]{ni, nj});
                }
            }
        }
    }
    
    public static void main(String[] args) {
        Problem04_NumberOfIslands sol = new Problem04_NumberOfIslands();
        char[][] g1 = {{'1','1','1','1','0'},{'1','1','0','1','0'},{'1','1','0','0','0'},{'0','0','0','0','0'}};
        System.out.println(sol.numIslands(g1)); // 1
        char[][] g2 = {{'1','1','0','0','0'},{'1','1','0','0','0'},{'0','0','1','0','0'},{'0','0','0','1','1'}};
        System.out.println(sol.numIslands(g2)); // 3
        char[][] g3 = {{'0'}};
        System.out.println(sol.numIslands(g3)); // 0
    }
}
