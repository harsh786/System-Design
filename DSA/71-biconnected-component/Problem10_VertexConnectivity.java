import java.util.*;

/**
 * Problem 10: Vertex Connectivity
 * 
 * Vertex connectivity κ(G) = minimum number of vertices whose removal disconnects G.
 * 
 * Properties:
 * - κ(G) = 0 if G is disconnected
 * - κ(G) = 1 if G has an articulation point
 * - κ(G) = n-1 for complete graph Kn
 * - Whitney's theorem: κ(G) ≤ λ(G) ≤ δ(G)
 *   (vertex conn ≤ edge conn ≤ min degree)
 * 
 * Computing exact vertex connectivity is expensive (requires max-flow).
 * Here we compute bounds and exact value for small graphs.
 * 
 * For the exact computation:
 * - κ(G) = min over all pairs (s,t) of max-flow in auxiliary graph
 * - Auxiliary: split each vertex v (except s,t) into v_in and v_out with capacity 1
 */
public class Problem10_VertexConnectivity {

    // Approximate vertex connectivity using bounds
    public static int[] vertexConnectivityBounds(int n, int[][] edges) {
        int[] degree = new int[n];
        List<List<Integer>> adj = new ArrayList<>();
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        
        for (int[] e : edges) {
            degree[e[0]]++; degree[e[1]]++;
            adj.get(e[0]).add(e[1]); adj.get(e[1]).add(e[0]);
        }
        
        // Upper bound: min degree
        int minDegree = Integer.MAX_VALUE;
        for (int d : degree) minDegree = Math.min(minDegree, d);
        
        // Lower bound via articulation points
        int lowerBound;
        if (!isConnected(n, adj)) {
            lowerBound = 0;
        } else if (hasArticulationPoint(n, adj)) {
            lowerBound = 1;
        } else {
            lowerBound = 2; // At least 2-connected
        }
        
        return new int[]{lowerBound, minDegree};
    }

    // Exact vertex connectivity for small graphs (brute force: try all subsets)
    public static int exactVertexConnectivity(int n, int[][] edges) {
        List<List<Integer>> adj = new ArrayList<>();
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        for (int[] e : edges) { adj.get(e[0]).add(e[1]); adj.get(e[1]).add(e[0]); }
        
        if (!isConnected(n, adj)) return 0;
        
        // Try removing k vertices for k = 0, 1, 2, ...
        for (int k = 0; k < n - 1; k++) {
            if (canDisconnectWithK(n, adj, k)) return k;
        }
        return n - 1; // Complete graph
    }

    private static boolean canDisconnectWithK(int n, List<List<Integer>> adj, int k) {
        // Try all subsets of size k
        return tryRemove(n, adj, k, 0, new boolean[n], 0);
    }

    private static boolean tryRemove(int n, List<List<Integer>> adj, int k, 
                                     int start, boolean[] removed, int count) {
        if (count == k) {
            return !isConnectedWithRemovals(n, adj, removed);
        }
        for (int i = start; i < n && n - i >= k - count; i++) {
            removed[i] = true;
            if (tryRemove(n, adj, k, i + 1, removed, count + 1)) return true;
            removed[i] = false;
        }
        return false;
    }

    private static boolean isConnectedWithRemovals(int n, List<List<Integer>> adj, boolean[] removed) {
        boolean[] visited = new boolean[n];
        int start = -1;
        for (int i = 0; i < n; i++) { if (!removed[i]) { start = i; break; } }
        if (start == -1) return true;
        
        Queue<Integer> q = new LinkedList<>();
        q.offer(start); visited[start] = true;
        int count = 1;
        while (!q.isEmpty()) {
            int u = q.poll();
            for (int v : adj.get(u)) {
                if (!visited[v] && !removed[v]) {
                    visited[v] = true; count++; q.offer(v);
                }
            }
        }
        int active = 0;
        for (int i = 0; i < n; i++) if (!removed[i]) active++;
        return count == active;
    }

    private static boolean isConnected(int n, List<List<Integer>> adj) {
        boolean[] visited = new boolean[n];
        Queue<Integer> q = new LinkedList<>();
        q.offer(0); visited[0] = true; int count = 1;
        while (!q.isEmpty()) {
            for (int v : adj.get(q.poll())) {
                if (!visited[v]) { visited[v] = true; count++; q.offer(v); }
            }
        }
        return count == n;
    }

    private static boolean hasArticulationPoint(int n, List<List<Integer>> adj) {
        int[] disc = new int[n], low = new int[n];
        boolean[] visited = new boolean[n];
        int[] timer = {0};
        return dfsAP(0, -1, adj, disc, low, visited, timer);
    }

    private static boolean dfsAP(int u, int par, List<List<Integer>> adj,
                                  int[] disc, int[] low, boolean[] visited, int[] timer) {
        visited[u] = true;
        disc[u] = low[u] = timer[0]++;
        int children = 0;
        for (int v : adj.get(u)) {
            if (!visited[v]) {
                children++;
                if (dfsAP(v, u, adj, disc, low, visited, timer)) return true;
                low[u] = Math.min(low[u], low[v]);
                if (par == -1 && children > 1) return true;
                if (par != -1 && low[v] >= disc[u]) return true;
            } else if (v != par) low[u] = Math.min(low[u], disc[v]);
        }
        return false;
    }

    public static void main(String[] args) {
        System.out.println("Vertex Connectivity Analysis");
        System.out.println("============================\n");

        // Petersen graph (3-connected)
        int[][] petersen = {{0,1},{1,2},{2,3},{3,4},{4,0},{5,7},{7,9},{9,6},{6,8},{8,5},
                           {0,5},{1,6},{2,7},{3,8},{4,9}};
        int[] bounds = vertexConnectivityBounds(10, petersen);
        System.out.printf("Petersen graph: κ in [%d, %d]%n", bounds[0], bounds[1]);
        // Exact for small graph
        int exact = exactVertexConnectivity(10, petersen);
        System.out.println("Exact κ = " + exact + " (known: 3)");

        // Path graph (κ = 1)
        int[][] path = {{0,1},{1,2},{2,3},{3,4}};
        exact = exactVertexConnectivity(5, path);
        System.out.println("\nPath graph: κ = " + exact);

        // Cycle (κ = 2)
        int[][] cycle = {{0,1},{1,2},{2,3},{3,4},{4,0}};
        exact = exactVertexConnectivity(5, cycle);
        System.out.println("Cycle graph: κ = " + exact);

        // K4 complete (κ = 3)
        int[][] k4 = {{0,1},{0,2},{0,3},{1,2},{1,3},{2,3}};
        exact = exactVertexConnectivity(4, k4);
        System.out.println("K4 complete: κ = " + exact);
    }
}
