import java.util.*;

/**
 * Problem 32: Swim in Rising Water (LeetCode 778)
 * 
 * Approach: Dijkstra/binary search + BFS. Minimize the max elevation on path from (0,0) to (n-1,n-1).
 * Time: O(N^2 log N), Space: O(N^2)
 * 
 * Production Analogy: Finding path through network where each link has a minimum latency threshold.
 */
public class Problem32_SwimInRisingWater {
    
    public int swimInWater(int[][] grid) {
        int n = grid.length;
        PriorityQueue<int[]> pq = new PriorityQueue<>((a,b) -> a[2]-b[2]);
        boolean[][] visited = new boolean[n][n];
        pq.offer(new int[]{0, 0, grid[0][0]});
        visited[0][0] = true;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!pq.isEmpty()) {
            int[] c = pq.poll();
            if (c[0] == n-1 && c[1] == n-1) return c[2];
            for (int[] d : dirs) {
                int ni = c[0]+d[0], nj = c[1]+d[1];
                if (ni>=0 && ni<n && nj>=0 && nj<n && !visited[ni][nj]) {
                    visited[ni][nj] = true;
                    pq.offer(new int[]{ni, nj, Math.max(c[2], grid[ni][nj])});
                }
            }
        }
        return -1;
    }
    
    public static void main(String[] args) {
        Problem32_SwimInRisingWater sol = new Problem32_SwimInRisingWater();
        System.out.println(sol.swimInWater(new int[][]{{0,2},{1,3}})); // 3
        System.out.println(sol.swimInWater(new int[][]{{0,1,2,3,4},{24,23,22,21,5},{12,13,14,15,16},{11,17,18,19,20},{10,9,8,7,6}})); // 16
    }
}
