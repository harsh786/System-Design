import java.util.*;

/**
 * Problem 5: Critical Connections in a Network (LeetCode 1192)
 * 
 * Same as finding bridges, but presented in LeetCode format.
 * 
 * Given n servers numbered 0 to n-1 connected by undirected edges,
 * find all critical connections (bridges) whose removal disconnects some servers.
 * 
 * This is the same algorithm as Problem02_Bridges but with LeetCode I/O format.
 */
public class Problem05_CriticalConnectionsNetwork {

    private int timer = 0;

    public List<List<Integer>> criticalConnections(int n, List<List<Integer>> connections) {
        List<List<Integer>> adj = new ArrayList<>();
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        for (List<Integer> conn : connections) {
            adj.get(conn.get(0)).add(conn.get(1));
            adj.get(conn.get(1)).add(conn.get(0));
        }

        int[] disc = new int[n], low = new int[n];
        Arrays.fill(disc, -1);
        List<List<Integer>> result = new ArrayList<>();

        dfs(0, -1, adj, disc, low, result);
        return result;
    }

    private void dfs(int u, int parent, List<List<Integer>> adj,
                     int[] disc, int[] low, List<List<Integer>> result) {
        disc[u] = low[u] = timer++;
        for (int v : adj.get(u)) {
            if (disc[v] == -1) {
                dfs(v, u, adj, disc, low, result);
                low[u] = Math.min(low[u], low[v]);
                if (low[v] > disc[u]) {
                    result.add(Arrays.asList(u, v));
                }
            } else if (v != parent) {
                low[u] = Math.min(low[u], disc[v]);
            }
        }
    }

    public static void main(String[] args) {
        Problem05_CriticalConnectionsNetwork solver = new Problem05_CriticalConnectionsNetwork();

        // LeetCode example
        List<List<Integer>> connections = Arrays.asList(
            Arrays.asList(0,1), Arrays.asList(1,2),
            Arrays.asList(2,0), Arrays.asList(1,3));

        List<List<Integer>> result = solver.criticalConnections(4, connections);
        System.out.println("LeetCode 1192: Critical Connections in a Network");
        System.out.println("n=4, connections=" + connections);
        System.out.println("Critical connections: " + result);
        // Expected: [[1,3]]

        // Larger example
        solver = new Problem05_CriticalConnectionsNetwork();
        List<List<Integer>> conn2 = Arrays.asList(
            Arrays.asList(0,1), Arrays.asList(1,2), Arrays.asList(2,3),
            Arrays.asList(3,0), Arrays.asList(3,4), Arrays.asList(4,5), Arrays.asList(5,3));
        System.out.println("\nn=6, connections=" + conn2);
        System.out.println("Critical connections: " + solver.criticalConnections(6, conn2));
    }
}
