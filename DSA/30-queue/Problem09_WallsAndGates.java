import java.util.*;

public class Problem09_WallsAndGates {
    public static void wallsAndGates(int[][] rooms) {
        int m = rooms.length, n = rooms[0].length;
        Queue<int[]> q = new LinkedList<>();
        for (int i = 0; i < m; i++) for (int j = 0; j < n; j++)
            if (rooms[i][j] == 0) q.offer(new int[]{i, j});
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!q.isEmpty()) {
            int[] c = q.poll();
            for (int[] d : dirs) {
                int r = c[0]+d[0], col = c[1]+d[1];
                if (r >= 0 && r < m && col >= 0 && col < n && rooms[r][col] == Integer.MAX_VALUE) {
                    rooms[r][col] = rooms[c[0]][c[1]] + 1; q.offer(new int[]{r, col});
                }
            }
        }
    }
    public static void main(String[] args) {
        int INF = Integer.MAX_VALUE;
        int[][] rooms = {{INF,-1,0,INF},{INF,INF,INF,-1},{INF,-1,INF,-1},{0,-1,INF,INF}};
        wallsAndGates(rooms);
        System.out.println(Arrays.deepToString(rooms));
    }
}
