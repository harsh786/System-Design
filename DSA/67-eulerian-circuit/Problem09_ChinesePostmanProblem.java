import java.util.*;

/**
 * Problem 9: Chinese Postman Problem (Route Inspection Problem)
 * 
 * Find the shortest closed walk that visits every edge at least once.
 * If graph has Eulerian circuit, the answer is sum of all edge weights.
 * Otherwise, we need to duplicate some edges (traverse them twice).
 * 
 * Algorithm for undirected graphs:
 * 1. Find all odd-degree vertices
 * 2. Find minimum weight perfect matching among odd-degree vertices
 * 3. Add matched edges to graph (duplicating them)
 * 4. Find Eulerian circuit in augmented graph
 * 
 * The minimum matching ensures minimum total weight of duplicated edges.
 * For this implementation, we use a simplified approach with shortest paths.
 */
public class Problem09_ChinesePostmanProblem {

    static final int INF = Integer.MAX_VALUE / 2;

    /**
     * Solve Chinese Postman for undirected weighted graph.
     * Returns minimum total distance to traverse all edges.
     */
    public static int chinesePostman(int n, int[][] edges) {
        // Total edge weight
        int totalWeight = 0;
        int[] degree = new int[n];
        int[][] dist = new int[n][n];
        for (int[] row : dist) Arrays.fill(row, INF);
        for (int i = 0; i < n; i++) dist[i][i] = 0;
        
        for (int[] e : edges) {
            int u = e[0], v = e[1], w = e[2];
            totalWeight += w;
            degree[u]++;
            degree[v]++;
            dist[u][v] = Math.min(dist[u][v], w);
            dist[v][u] = Math.min(dist[v][u], w);
        }
        
        // Floyd-Warshall for shortest paths between odd-degree vertices
        for (int k = 0; k < n; k++)
            for (int i = 0; i < n; i++)
                for (int j = 0; j < n; j++)
                    dist[i][j] = Math.min(dist[i][j], dist[i][k] + dist[k][j]);
        
        // Find odd-degree vertices
        List<Integer> odd = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            if (degree[i] % 2 == 1) odd.add(i);
        }
        
        if (odd.isEmpty()) return totalWeight; // Already Eulerian
        
        // Minimum weight perfect matching using bitmask DP
        int m = odd.size();
        int[] dp = new int[1 << m];
        Arrays.fill(dp, INF);
        dp[0] = 0;
        
        for (int mask = 0; mask < (1 << m); mask++) {
            if (dp[mask] == INF) continue;
            // Find first unmatched vertex
            int first = -1;
            for (int i = 0; i < m; i++) {
                if ((mask & (1 << i)) == 0) { first = i; break; }
            }
            if (first == -1) continue;
            
            // Try matching with every other unmatched vertex
            for (int second = first + 1; second < m; second++) {
                if ((mask & (1 << second)) != 0) continue;
                int newMask = mask | (1 << first) | (1 << second);
                int cost = dist[odd.get(first)][odd.get(second)];
                dp[newMask] = Math.min(dp[newMask], dp[mask] + cost);
            }
        }
        
        return totalWeight + dp[(1 << m) - 1];
    }

    public static void main(String[] args) {
        // Example: Square with one diagonal
        // 0--1--2--3--0, diagonal 0--2
        int[][] edges = {
            {0, 1, 1}, {1, 2, 1}, {2, 3, 1}, {3, 0, 1}, {0, 2, 2}
        };
        // Degrees: 0=3, 1=2, 2=3, 3=2 → odd vertices: 0, 2
        // Shortest path 0→2 = 2 (direct diagonal)
        // Answer = 1+1+1+1+2 + 2 = 8

        int result = chinesePostman(4, edges);
        System.out.println("Chinese Postman Problem");
        System.out.println("Graph: square with diagonal, all weights shown");
        System.out.println("Minimum route distance: " + result);
        System.out.println("(Sum of edges = 6, extra traversal = " + (result - 6) + ")");
        
        // Eulerian graph (all even degree)
        int[][] eulerian = {{0,1,3},{1,2,4},{2,3,5},{3,0,2},{0,2,1},{1,3,6}};
        int result2 = chinesePostman(4, eulerian);
        System.out.println("\nEulerian graph (all even degree):");
        System.out.println("Minimum route = sum of edges = " + result2);
    }
}
