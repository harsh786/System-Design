import java.util.*;

public class Problem11_ShortestPathInBinaryMatrix {
    public static int shortestPathBinaryMatrix(int[][] grid) {
        int n = grid.length;
        if (grid[0][0] == 1 || grid[n-1][n-1] == 1) return -1;
        Queue<int[]> q = new LinkedList<>();
        q.offer(new int[]{0,0,1}); grid[0][0] = 1;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0},{1,1},{1,-1},{-1,1},{-1,-1}};
        while (!q.isEmpty()) {
            int[] c = q.poll();
            if (c[0] == n-1 && c[1] == n-1) return c[2];
            for (int[] d : dirs) {
                int r = c[0]+d[0], col = c[1]+d[1];
                if (r >= 0 && r < n && col >= 0 && col < n && grid[r][col] == 0) {
                    grid[r][col] = 1; q.offer(new int[]{r, col, c[2]+1});
                }
            }
        }
        return -1;
    }
    public static void main(String[] args) {
        System.out.println(shortestPathBinaryMatrix(new int[][]{{0,0,0},{1,1,0},{1,1,0}})); // 4
    }
}
