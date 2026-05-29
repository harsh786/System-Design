import java.util.*;

/**
 * Problem 38: Minimum Cost to Connect All Points - Kruskal's (LeetCode 1584 variant)
 * 
 * Same as Problem 10 but with explicit Kruskal's implementation and optimized edge generation.
 * Uses priority queue instead of full sort for large inputs.
 * 
 * Time: O(n² * log(n²)), Space: O(n²)
 * 
 * Production Analogy: Building minimum-cost WAN connecting geographically distributed offices.
 */
public class Problem38_MinCostToConnectAllPointsKruskal {
    
    int[] parent, rank;
    
    public int minCostConnectPoints(int[][] points) {
        int n = points.length;
        // Use PQ for potentially better constant factor with early termination
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[0] - b[0]);
        for (int i = 0; i < n; i++)
            for (int j = i + 1; j < n; j++) {
                int dist = Math.abs(points[i][0]-points[j][0]) + Math.abs(points[i][1]-points[j][1]);
                pq.offer(new int[]{dist, i, j});
            }
        
        parent = new int[n]; rank = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        
        int cost = 0, edges = 0;
        while (edges < n - 1) {
            int[] e = pq.poll();
            if (union(e[1], e[2])) {
                cost += e[0];
                edges++;
            }
        }
        return cost;
    }
    
    private int find(int x) {
        if (parent[x] != x) parent[x] = find(parent[x]);
        return parent[x];
    }
    
    private boolean union(int x, int y) {
        int px = find(x), py = find(y);
        if (px == py) return false;
        if (rank[px] < rank[py]) parent[px] = py;
        else if (rank[px] > rank[py]) parent[py] = px;
        else { parent[py] = px; rank[px]++; }
        return true;
    }
    
    public static void main(String[] args) {
        Problem38_MinCostToConnectAllPointsKruskal sol = new Problem38_MinCostToConnectAllPointsKruskal();
        System.out.println(sol.minCostConnectPoints(new int[][]{{0,0},{2,2},{3,10},{5,2},{7,0}})); // 20
        System.out.println(sol.minCostConnectPoints(new int[][]{{0,0}})); // 0
    }
}
