import java.util.*;

/**
 * Problem 13: Min Cost to Connect All Points (LeetCode 1584) - Prim's MST
 * 
 * Approach: Prim's algorithm with priority queue. Manhattan distance as edge weight.
 * Time: O(N^2 log N), Space: O(N^2)
 * 
 * Production Analogy: Minimizing total cable length to connect data centers in a WAN.
 */
public class Problem13_MinCostConnectAllPoints {
    
    public int minCostConnectPoints(int[][] points) {
        int n = points.length, cost = 0, connected = 0;
        boolean[] visited = new boolean[n];
        PriorityQueue<int[]> pq = new PriorityQueue<>((a,b) -> a[0] - b[0]);
        pq.offer(new int[]{0, 0});
        while (connected < n) {
            int[] curr = pq.poll();
            if (visited[curr[1]]) continue;
            visited[curr[1]] = true;
            cost += curr[0];
            connected++;
            for (int i = 0; i < n; i++) {
                if (!visited[i]) {
                    int dist = Math.abs(points[curr[1]][0]-points[i][0]) + Math.abs(points[curr[1]][1]-points[i][1]);
                    pq.offer(new int[]{dist, i});
                }
            }
        }
        return cost;
    }
    
    public static void main(String[] args) {
        Problem13_MinCostConnectAllPoints sol = new Problem13_MinCostConnectAllPoints();
        System.out.println(sol.minCostConnectPoints(new int[][]{{0,0},{2,2},{3,10},{5,2},{7,0}})); // 20
        System.out.println(sol.minCostConnectPoints(new int[][]{{3,12},{-2,5},{-4,1}})); // 18
        System.out.println(sol.minCostConnectPoints(new int[][]{{0,0}})); // 0
    }
}
