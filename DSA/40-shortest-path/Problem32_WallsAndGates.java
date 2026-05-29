import java.util.*;

/**
 * Problem: Walls and Gates
 * Fill each empty room with distance to nearest gate.
 *
 * Approach: Multi-source BFS from all gates
 *
 * Time Complexity: O(m*n)
 * Space Complexity: O(m*n)
 *
 * Production Analogy: Computing nearest exit distance for evacuation planning.
 */
public class Problem32_WallsAndGates {

    public void wallsAndGates(int[][] rooms) {
        int m = rooms.length, n = rooms[0].length, INF = Integer.MAX_VALUE;
        Queue<int[]> q = new LinkedList<>();
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                if (rooms[i][j] == 0) q.offer(new int[]{i, j});

        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!q.isEmpty()) {
            int[] cur = q.poll();
            for (int[] d : dirs) {
                int nr = cur[0]+d[0], nc = cur[1]+d[1];
                if (nr>=0&&nr<m&&nc>=0&&nc<n&&rooms[nr][nc]==INF) {
                    rooms[nr][nc] = rooms[cur[0]][cur[1]] + 1;
                    q.offer(new int[]{nr, nc});
                }
            }
        }
    }

    public static void main(String[] args) {
        Problem32_WallsAndGates solver = new Problem32_WallsAndGates();
        int INF = Integer.MAX_VALUE;
        int[][] rooms = {{INF,-1,0,INF},{INF,INF,INF,-1},{INF,-1,INF,-1},{0,-1,INF,INF}};
        solver.wallsAndGates(rooms);
        for (int[] row : rooms) System.out.println(Arrays.toString(row));
    }
}
