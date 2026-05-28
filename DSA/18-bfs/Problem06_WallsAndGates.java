import java.util.*;

/**
 * Problem: Walls and Gates (LeetCode 286)
 * Approach: Multi-source BFS from all gates simultaneously
 * Time: O(M*N), Space: O(M*N)
 * Production Analogy: Computing nearest CDN edge node distance for all users
 */
public class Problem06_WallsAndGates {
    public void wallsAndGates(int[][] rooms) {
        int m = rooms.length, n = rooms[0].length;
        Queue<int[]> q = new LinkedList<>();
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                if (rooms[i][j] == 0) q.offer(new int[]{i, j});
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!q.isEmpty()) {
            int[] cell = q.poll();
            for (int[] d : dirs) {
                int ni = cell[0]+d[0], nj = cell[1]+d[1];
                if (ni >= 0 && ni < m && nj >= 0 && nj < n && rooms[ni][nj] == Integer.MAX_VALUE) {
                    rooms[ni][nj] = rooms[cell[0]][cell[1]] + 1;
                    q.offer(new int[]{ni, nj});
                }
            }
        }
    }

    public static void main(String[] args) {
        int INF = Integer.MAX_VALUE;
        int[][] rooms = {{INF,-1,0,INF},{INF,INF,INF,-1},{INF,-1,INF,-1},{0,-1,INF,INF}};
        new Problem06_WallsAndGates().wallsAndGates(rooms);
        for (int[] row : rooms) System.out.println(Arrays.toString(row));
    }
}
