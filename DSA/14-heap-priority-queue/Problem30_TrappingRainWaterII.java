import java.util.*;

/**
 * Problem 30: Trapping Rain Water II (LeetCode 407)
 * 
 * Approach: BFS from borders using min-heap. Process lowest boundary cell first,
 * water level is determined by the lowest unvisited boundary.
 * 
 * Time Complexity: O(M*N log(M*N))
 * Space Complexity: O(M*N)
 * 
 * Production Analogy: Capacity planning - determining maximum throughput bottlenecks
 * in a 2D grid of interconnected service nodes.
 */
public class Problem30_TrappingRainWaterII {
    
    public int trapRainWater(int[][] heightMap) {
        int m = heightMap.length, n = heightMap[0].length;
        if (m < 3 || n < 3) return 0;
        
        boolean[][] visited = new boolean[m][n];
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[2] - b[2]);
        
        // Add borders
        for (int i = 0; i < m; i++) {
            pq.offer(new int[]{i, 0, heightMap[i][0]}); visited[i][0] = true;
            pq.offer(new int[]{i, n-1, heightMap[i][n-1]}); visited[i][n-1] = true;
        }
        for (int j = 1; j < n-1; j++) {
            pq.offer(new int[]{0, j, heightMap[0][j]}); visited[0][j] = true;
            pq.offer(new int[]{m-1, j, heightMap[m-1][j]}); visited[m-1][j] = true;
        }
        
        int water = 0;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!pq.isEmpty()) {
            int[] curr = pq.poll();
            for (int[] d : dirs) {
                int nr = curr[0]+d[0], nc = curr[1]+d[1];
                if (nr < 0 || nr >= m || nc < 0 || nc >= n || visited[nr][nc]) continue;
                visited[nr][nc] = true;
                water += Math.max(0, curr[2] - heightMap[nr][nc]);
                pq.offer(new int[]{nr, nc, Math.max(curr[2], heightMap[nr][nc])});
            }
        }
        return water;
    }
    
    public static void main(String[] args) {
        Problem30_TrappingRainWaterII sol = new Problem30_TrappingRainWaterII();
        System.out.println(sol.trapRainWater(new int[][]{
            {1,4,3,1,3,2},{3,2,1,3,2,4},{2,3,3,2,3,1}})); // 4
        System.out.println(sol.trapRainWater(new int[][]{
            {3,3,3,3,3},{3,2,2,2,3},{3,2,1,2,3},{3,2,2,2,3},{3,3,3,3,3}})); // 10
    }
}
