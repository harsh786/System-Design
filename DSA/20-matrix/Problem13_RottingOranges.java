import java.util.*;

/**
 * Problem 13: Rotting Oranges
 * 
 * Every minute, fresh oranges adjacent to rotten ones become rotten. Return minutes
 * until no fresh orange remains, or -1 if impossible.
 *
 * Approach: Multi-source BFS from all initially rotten oranges simultaneously.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(m * n)
 *
 * Production Analogy: Virus/failure propagation in a network. Modeling cascade failures
 * in microservices where one failing service causes adjacent services to fail over time.
 */
public class Problem13_RottingOranges {

    public static int orangesRotting(int[][] grid) {
        int m = grid.length, n = grid[0].length, fresh = 0, minutes = 0;
        Queue<int[]> queue = new LinkedList<>();
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                if (grid[i][j] == 2) queue.offer(new int[]{i, j});
                else if (grid[i][j] == 1) fresh++;
            }
        int[] dx = {0,0,1,-1}, dy = {1,-1,0,0};
        while (!queue.isEmpty() && fresh > 0) {
            minutes++;
            int size = queue.size();
            while (size-- > 0) {
                int[] cell = queue.poll();
                for (int d = 0; d < 4; d++) {
                    int ni = cell[0]+dx[d], nj = cell[1]+dy[d];
                    if (ni >= 0 && ni < m && nj >= 0 && nj < n && grid[ni][nj] == 1) {
                        grid[ni][nj] = 2;
                        fresh--;
                        queue.offer(new int[]{ni, nj});
                    }
                }
            }
        }
        return fresh == 0 ? minutes : -1;
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + orangesRotting(new int[][]{{2,1,1},{1,1,0},{0,1,1}})); // 4
        System.out.println("Test 2: " + orangesRotting(new int[][]{{2,1,1},{0,1,1},{1,0,1}})); // -1
        System.out.println("Test 3: " + orangesRotting(new int[][]{{0,2}})); // 0
    }
}
