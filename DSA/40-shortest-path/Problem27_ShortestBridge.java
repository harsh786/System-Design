import java.util.*;

/**
 * Problem: Shortest Bridge
 * Find shortest bridge (flipping 0s to 1s) between two islands.
 *
 * Approach: DFS to find one island, then BFS to expand until reaching second island
 *
 * Time Complexity: O(m*n)
 * Space Complexity: O(m*n)
 *
 * Production Analogy: Minimum infrastructure to connect two isolated networks.
 */
public class Problem27_ShortestBridge {

    public int shortestBridge(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        Queue<int[]> q = new LinkedList<>();
        boolean found = false;

        for (int i = 0; i < m && !found; i++)
            for (int j = 0; j < n && !found; j++)
                if (grid[i][j] == 1) { dfs(grid, i, j, m, n, q); found = true; }

        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        int steps = 0;
        while (!q.isEmpty()) {
            int size = q.size();
            for (int i = 0; i < size; i++) {
                int[] cur = q.poll();
                for (int[] d : dirs) {
                    int nr = cur[0]+d[0], nc = cur[1]+d[1];
                    if (nr>=0&&nr<m&&nc>=0&&nc<n&&grid[nr][nc]!=2) {
                        if (grid[nr][nc] == 1) return steps;
                        grid[nr][nc] = 2; q.offer(new int[]{nr, nc});
                    }
                }
            }
            steps++;
        }
        return -1;
    }

    private void dfs(int[][] grid, int r, int c, int m, int n, Queue<int[]> q) {
        if (r<0||r>=m||c<0||c>=n||grid[r][c]!=1) return;
        grid[r][c] = 2; q.offer(new int[]{r, c});
        dfs(grid,r+1,c,m,n,q); dfs(grid,r-1,c,m,n,q); dfs(grid,r,c+1,m,n,q); dfs(grid,r,c-1,m,n,q);
    }

    public static void main(String[] args) {
        Problem27_ShortestBridge solver = new Problem27_ShortestBridge();
        System.out.println(solver.shortestBridge(new int[][]{{0,1},{1,0}})); // 1
    }
}
