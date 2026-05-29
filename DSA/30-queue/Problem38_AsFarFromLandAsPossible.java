import java.util.*;

public class Problem38_AsFarFromLandAsPossible {
    public static int maxDistance(int[][] grid) {
        int n = grid.length;
        Queue<int[]> q = new LinkedList<>();
        for (int i = 0; i < n; i++) for (int j = 0; j < n; j++) if (grid[i][j] == 1) q.offer(new int[]{i, j});
        if (q.size() == 0 || q.size() == n * n) return -1;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        int dist = -1;
        while (!q.isEmpty()) {
            dist++;
            for (int sz = q.size(); sz > 0; sz--) {
                int[] c = q.poll();
                for (int[] d : dirs) {
                    int r = c[0]+d[0], col = c[1]+d[1];
                    if (r >= 0 && r < n && col >= 0 && col < n && grid[r][col] == 0) {
                        grid[r][col] = 1; q.offer(new int[]{r, col});
                    }
                }
            }
        }
        return dist;
    }
    public static void main(String[] args) {
        System.out.println(maxDistance(new int[][]{{1,0,1},{0,0,0},{1,0,1}})); // 2
    }
}
