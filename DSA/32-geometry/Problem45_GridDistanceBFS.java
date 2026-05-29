import java.util.*;

public class Problem45_GridDistanceBFS {
    // Find shortest distance from each cell to nearest target cell
    public static int[][] gridDistance(int[][] grid, int target) {
        int m = grid.length, n = grid[0].length;
        int[][] dist = new int[m][n];
        for (int[] row : dist) Arrays.fill(row, -1);
        Queue<int[]> q = new LinkedList<>();
        for (int i = 0; i < m; i++) for (int j = 0; j < n; j++)
            if (grid[i][j] == target) { dist[i][j] = 0; q.offer(new int[]{i, j}); }
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!q.isEmpty()) {
            int[] c = q.poll();
            for (int[] d : dirs) {
                int r = c[0]+d[0], col = c[1]+d[1];
                if (r >= 0 && r < m && col >= 0 && col < n && dist[r][col] == -1) {
                    dist[r][col] = dist[c[0]][c[1]] + 1; q.offer(new int[]{r, col});
                }
            }
        }
        return dist;
    }
    public static void main(String[] args) {
        int[][] grid = {{0,0,0},{0,1,0},{0,0,0}};
        int[][] res = gridDistance(grid, 1);
        for (int[] row : res) System.out.println(Arrays.toString(row));
    }
}
