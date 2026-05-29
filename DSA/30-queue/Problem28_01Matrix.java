import java.util.*;

public class Problem28_01Matrix {
    public static int[][] updateMatrix(int[][] mat) {
        int m = mat.length, n = mat[0].length;
        int[][] dist = new int[m][n];
        Queue<int[]> q = new LinkedList<>();
        for (int i = 0; i < m; i++) for (int j = 0; j < n; j++) {
            if (mat[i][j] == 0) q.offer(new int[]{i, j});
            else dist[i][j] = Integer.MAX_VALUE;
        }
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!q.isEmpty()) {
            int[] c = q.poll();
            for (int[] d : dirs) {
                int r = c[0]+d[0], col = c[1]+d[1];
                if (r >= 0 && r < m && col >= 0 && col < n && dist[r][col] > dist[c[0]][c[1]] + 1) {
                    dist[r][col] = dist[c[0]][c[1]] + 1; q.offer(new int[]{r, col});
                }
            }
        }
        return dist;
    }
    public static void main(String[] args) {
        int[][] res = updateMatrix(new int[][]{{0,0,0},{0,1,0},{1,1,1}});
        System.out.println(Arrays.deepToString(res));
    }
}
