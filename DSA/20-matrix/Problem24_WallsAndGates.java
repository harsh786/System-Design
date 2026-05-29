import java.util.*;

/**
 * Problem 24: Walls and Gates
 * 
 * Grid with -1 (wall), 0 (gate), INF (empty room). Fill each empty room with
 * distance to nearest gate.
 *
 * Approach: Multi-source BFS from all gates simultaneously.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(m * n)
 *
 * Production Analogy: Computing shortest distance to nearest exit in building evacuation
 * planning. Or nearest cache server distance in a CDN grid topology.
 */
public class Problem24_WallsAndGates {

    public static void wallsAndGates(int[][] rooms) {
        int m = rooms.length, n = rooms[0].length;
        Queue<int[]> queue = new LinkedList<>();
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                if (rooms[i][j] == 0) queue.offer(new int[]{i, j});

        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!queue.isEmpty()) {
            int[] cell = queue.poll();
            for (int[] d : dirs) {
                int ni = cell[0]+d[0], nj = cell[1]+d[1];
                if (ni >= 0 && ni < m && nj >= 0 && nj < n && rooms[ni][nj] == Integer.MAX_VALUE) {
                    rooms[ni][nj] = rooms[cell[0]][cell[1]] + 1;
                    queue.offer(new int[]{ni, nj});
                }
            }
        }
    }

    public static void main(String[] args) {
        int INF = Integer.MAX_VALUE;
        int[][] rooms = {{INF,-1,0,INF},{INF,INF,INF,-1},{INF,-1,INF,-1},{0,-1,INF,INF}};
        wallsAndGates(rooms);
        System.out.println("Test 1: " + Arrays.deepToString(rooms));
        // [[3,-1,0,1],[2,2,1,-1],[1,-1,2,-1],[0,-1,3,4]]
    }
}
