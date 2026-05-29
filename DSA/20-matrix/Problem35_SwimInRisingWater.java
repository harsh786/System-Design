import java.util.*;

/**
 * Problem 35: Swim in Rising Water
 * 
 * Grid of elevations. At time t, can swim through cells with elevation <= t.
 * Find minimum t to reach from (0,0) to (n-1,n-1).
 *
 * Approach: Binary search on t + BFS/DFS to check connectivity, or Dijkstra/min-heap.
 * Using min-heap (modified Dijkstra): always expand lowest elevation cell.
 *
 * Time Complexity: O(n^2 * log(n))
 * Space Complexity: O(n^2)
 *
 * Production Analogy: Finding the minimum SLA guarantee needed to ensure a path
 * exists between two services through a chain of intermediaries with varying latencies.
 */
public class Problem35_SwimInRisingWater {

    public static int swimInWater(int[][] grid) {
        int n = grid.length;
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[2] - b[2]);
        pq.offer(new int[]{0, 0, grid[0][0]});
        boolean[][] visited = new boolean[n][n];
        visited[0][0] = true;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!pq.isEmpty()) {
            int[] cur = pq.poll();
            if (cur[0] == n-1 && cur[1] == n-1) return cur[2];
            for (int[] d : dirs) {
                int ni = cur[0]+d[0], nj = cur[1]+d[1];
                if (ni >= 0 && ni < n && nj >= 0 && nj < n && !visited[ni][nj]) {
                    visited[ni][nj] = true;
                    pq.offer(new int[]{ni, nj, Math.max(cur[2], grid[ni][nj])});
                }
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + swimInWater(new int[][]{{0,2},{1,3}})); // 3
        System.out.println("Test 2: " + swimInWater(new int[][]{{0,1,2,3,4},{24,23,22,21,5},{12,13,14,15,16},{11,17,18,19,20},{10,9,8,7,6}})); // 16
    }
}
