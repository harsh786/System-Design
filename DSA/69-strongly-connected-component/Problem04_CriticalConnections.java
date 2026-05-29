import java.util.*;

/**
 * Problem 4: Critical Connections in a Network (LeetCode 1192)
 * 
 * Find all bridges (critical connections) in an undirected graph.
 * A bridge is an edge whose removal disconnects the graph.
 * 
 * Algorithm: Modified Tarjan's using low-link values.
 * Edge (u,v) is a bridge if low[v] > disc[u]
 * (meaning v cannot reach u or any ancestor of u without using edge u-v)
 * 
 * Time: O(V + E), Space: O(V + E)
 */
public class Problem04_CriticalConnections {

    private int timer = 0;

    public List<List<Integer>> criticalConnections(int n, List<List<Integer>> connections) {
        List<List<Integer>> graph = new ArrayList<>();
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (List<Integer> conn : connections) {
            graph.get(conn.get(0)).add(conn.get(1));
            graph.get(conn.get(1)).add(conn.get(0));
        }
        
        int[] disc = new int[n], low = new int[n];
        Arrays.fill(disc, -1);
        List<List<Integer>> bridges = new ArrayList<>();
        
        dfs(0, -1, graph, disc, low, bridges);
        return bridges;
    }

    private void dfs(int u, int parent, List<List<Integer>> graph, 
                     int[] disc, int[] low, List<List<Integer>> bridges) {
        disc[u] = low[u] = timer++;
        
        for (int v : graph.get(u)) {
            if (v == parent) continue; // Skip the edge we came from
            if (disc[v] == -1) {
                dfs(v, u, graph, disc, low, bridges);
                low[u] = Math.min(low[u], low[v]);
                // Bridge condition: v cannot reach u's ancestors
                if (low[v] > disc[u]) {
                    bridges.add(Arrays.asList(u, v));
                }
            } else {
                low[u] = Math.min(low[u], disc[v]);
            }
        }
    }

    public static void main(String[] args) {
        Problem04_CriticalConnections solver = new Problem04_CriticalConnections();
        
        // Example: 4 nodes, edge 1-3 is a bridge
        int n = 4;
        List<List<Integer>> connections = Arrays.asList(
            Arrays.asList(0, 1), Arrays.asList(1, 2),
            Arrays.asList(2, 0), Arrays.asList(1, 3));
        
        List<List<Integer>> result = solver.criticalConnections(n, connections);
        System.out.println("LeetCode 1192: Critical Connections");
        System.out.println("Connections: " + connections);
        System.out.println("Bridges: " + result);
        // Expected: [[1, 3]]

        // Example 2: No bridges (all edges in cycles)
        solver = new Problem04_CriticalConnections();
        List<List<Integer>> conn2 = Arrays.asList(
            Arrays.asList(0,1), Arrays.asList(1,2), 
            Arrays.asList(2,3), Arrays.asList(3,0));
        System.out.println("\nSquare graph - Bridges: " + solver.criticalConnections(4, conn2));
    }
}
