import java.util.*;

public class Problem27_ShortestBridge {
    public static int shortestBridge(int[][] grid) {
        int n = grid.length;
        Queue<int[]> q = new LinkedList<>();
        boolean[][] visited = new boolean[n][n];
        boolean found = false;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        // DFS to find first island
        for (int i = 0; i < n && !found; i++) for (int j = 0; j < n && !found; j++) {
            if (grid[i][j] == 1) { dfs(grid, visited, q, i, j, dirs); found = true; }
        }
        // BFS to expand
        int steps = 0;
        while (!q.isEmpty()) {
            for (int sz = q.size(); sz > 0; sz--) {
                int[] c = q.poll();
                for (int[] d : dirs) {
                    int r = c[0]+d[0], col = c[1]+d[1];
                    if (r >= 0 && r < n && col >= 0 && col < n && !visited[r][col]) {
                        if (grid[r][col] == 1) return steps;
                        visited[r][col] = true; q.offer(new int[]{r, col});
                    }
                }
            }
            steps++;
        }
        return -1;
    }
    static void dfs(int[][] grid, boolean[][] visited, Queue<int[]> q, int i, int j, int[][] dirs) {
        if (i < 0 || i >= grid.length || j < 0 || j >= grid.length || visited[i][j] || grid[i][j] == 0) return;
        visited[i][j] = true; q.offer(new int[]{i, j});
        for (int[] d : dirs) dfs(grid, visited, q, i+d[0], j+d[1], dirs);
    }
    public static void main(String[] args) {
        System.out.println(shortestBridge(new int[][]{{0,1},{1,0}})); // 1
    }
}
