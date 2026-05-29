import java.util.*;

/**
 * Problem: Bellman-Ford Algorithm
 * Single source shortest path with negative weights, detect negative cycles.
 *
 * Approach: Relax all edges V-1 times, check for negative cycle on V-th pass
 *
 * Time Complexity: O(V * E)
 * Space Complexity: O(V)
 *
 * Production Analogy: Detecting arbitrage opportunities in currency exchange networks.
 */
public class Problem10_BellmanFordAlgorithm {

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
                throw new RuntimeException("Negative cycle detected");

        return dist;
    }

    public static void main(String[] args) {
        Problem10_BellmanFordAlgorithm solver = new Problem10_BellmanFordAlgorithm();
        int[][] edges = {{0,1,4},{0,2,5},{1,2,-3},{2,3,4}};
        System.out.println(Arrays.toString(solver.bellmanFord(4, edges, 0)));
    }
}
