import java.util.*;

public class Problem08_RottingOranges {
    public static int orangesRotting(int[][] grid) {
        int m = grid.length, n = grid[0].length, fresh = 0, time = 0;
        Queue<int[]> q = new LinkedList<>();
        for (int i = 0; i < m; i++) for (int j = 0; j < n; j++) {
            if (grid[i][j] == 2) q.offer(new int[]{i, j});
            else if (grid[i][j] == 1) fresh++;
        }
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!q.isEmpty() && fresh > 0) {
            time++;
            for (int sz = q.size(); sz > 0; sz--) {
                int[] c = q.poll();
                for (int[] d : dirs) {
                    int r = c[0]+d[0], col = c[1]+d[1];
                    if (r >= 0 && r < m && col >= 0 && col < n && grid[r][col] == 1) {
                        grid[r][col] = 2; fresh--; q.offer(new int[]{r, col});
                    }
                }
            }
        }
        return fresh == 0 ? time : -1;
    }
    public static void main(String[] args) {
        System.out.println(orangesRotting(new int[][]{{2,1,1},{1,1,0},{0,1,1}})); // 4
    }
}
