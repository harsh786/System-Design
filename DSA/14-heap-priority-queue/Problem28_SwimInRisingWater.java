import java.util.*;

/**
 * Problem 28: Swim in Rising Water (LeetCode 778)
 * 
 * Approach: Modified Dijkstra - min-heap by max elevation along path.
 * 
 * Time Complexity: O(N^2 log N)
 * Space Complexity: O(N^2)
 * 
 * Production Analogy: Finding the time at which a network path becomes fully available
 * when nodes come online at different times.
 */
public class Problem28_SwimInRisingWater {
    
    public int swimInWater(int[][] grid) {
        int n = grid.length;
        boolean[][] visited = new boolean[n][n];
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[2] - b[2]);
        pq.offer(new int[]{0, 0, grid[0][0]});
        visited[0][0] = true;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        
        while (!pq.isEmpty()) {
            int[] curr = pq.poll();
            int r = curr[0], c = curr[1], t = curr[2];
            if (r == n - 1 && c == n - 1) return t;
            for (int[] d : dirs) {
                int nr = r + d[0], nc = c + d[1];
                if (nr < 0 || nr >= n || nc < 0 || nc >= n || visited[nr][nc]) continue;
                visited[nr][nc] = true;
                pq.offer(new int[]{nr, nc, Math.max(t, grid[nr][nc])});
            }
        }
        return -1;
    }
    
    public static void main(String[] args) {
        Problem28_SwimInRisingWater sol = new Problem28_SwimInRisingWater();
        System.out.println(sol.swimInWater(new int[][]{{0,2},{1,3}})); // 3
        System.out.println(sol.swimInWater(new int[][]{{0,1,2,3,4},{24,23,22,21,5},{12,13,14,15,16},{11,17,18,19,20},{10,9,8,7,6}})); // 16
    }
}
