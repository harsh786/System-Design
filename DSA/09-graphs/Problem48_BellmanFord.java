import java.util.*;

/**
 * Problem 48: Bellman-Ford Algorithm
 * 
 * Approach: Relax all edges V-1 times. Handles negative weights. Detect negative cycles on V-th pass.
 * Time: O(V * E), Space: O(V)
 * 
 * Production Analogy: Computing shortest routes in financial networks where costs can be negative (rebates).
 * Negative cycle = arbitrage opportunity / infinite loop detection.
 */
public class Problem48_BellmanFord {
    
    public int[] bellmanFord(int n, int[][] edges, int src) {
        int[] dist = new int[n];
        Arrays.fill(dist, Integer.MAX_VALUE);
        dist[src] = 0;
        for (int i = 0; i < n - 1; i++)
            for (int[] e : edges)
                if (dist[e[0]] != Integer.MAX_VALUE && dist[e[0]] + e[2] < dist[e[1]])
                    dist[e[1]] = dist[e[0]] + e[2];
        // Check negative cycle
        for (int[] e : edges)
            if (dist[e[0]] != Integer.MAX_VALUE && dist[e[0]] + e[2] < dist[e[1]])
                return null; // negative cycle
        return dist;
    }
    
    public static void main(String[] args) {
        Problem48_BellmanFord sol = new Problem48_BellmanFord();
        // 5 nodes, edges with negative weight
        int[][] edges = {{0,1,6},{0,2,7},{1,2,8},{1,3,5},{1,4,-4},{2,3,-3},{2,4,9},{3,1,-2},{4,0,2},{4,3,7}};
        int[] dist = sol.bellmanFord(5, edges, 0);
        System.out.println(Arrays.toString(dist)); // [0, 2, 7, 4, -2]
        
        // Negative cycle
        int[][] edges2 = {{0,1,1},{1,2,-1},{2,0,-1}};
        System.out.println(sol.bellmanFord(3, edges2, 0) == null ? "Negative cycle" : "No cycle");
    }
}
