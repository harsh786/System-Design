import java.util.*;

/**
 * Problem 9: Redundant Connection Bridge Check
 * 
 * Given a graph that started as a tree with one extra edge added,
 * find the edge that can be removed to make it a tree again.
 * If multiple answers, return the last one in the input.
 * 
 * LeetCode 684 variant + bridge analysis:
 * - The redundant edge creates a cycle
 * - After removal, there should be no bridges (tree has all "bridges")
 * - We use Union-Find to detect the cycle-forming edge
 * 
 * Extended: After finding redundant edge, verify graph structure.
 */
public class Problem09_RedundantConnectionBridge {

    // Union-Find for cycle detection
    private int[] parent, rank;

    private int find(int x) {
        while (parent[x] != x) { parent[x] = parent[parent[x]]; x = parent[x]; }
        return x;
    }

    private boolean union(int a, int b) {
        int pa = find(a), pb = find(b);
        if (pa == pb) return false; // Cycle detected
        if (rank[pa] < rank[pb]) { int t = pa; pa = pb; pb = t; }
        parent[pb] = pa;
        if (rank[pa] == rank[pb]) rank[pa]++;
        return true;
    }

    public int[] findRedundantConnection(int[][] edges) {
        int n = edges.length;
        parent = new int[n + 1];
        rank = new int[n + 1];
        for (int i = 0; i <= n; i++) parent[i] = i;

        for (int[] edge : edges) {
            if (!union(edge[0], edge[1])) {
                return edge; // This edge creates a cycle
            }
        }
        return new int[0];
    }

    // After removing redundant edge, count bridges (should be n-1 for tree)
    public int countBridgesAfterRemoval(int n, int[][] edges, int[] removedEdge) {
        List<List<Integer>> adj = new ArrayList<>();
        for (int i = 0; i <= n; i++) adj.add(new ArrayList<>());
        for (int[] e : edges) {
            if (e[0] == removedEdge[0] && e[1] == removedEdge[1]) continue;
            adj.get(e[0]).add(e[1]);
            adj.get(e[1]).add(e[0]);
        }
        
        int[] disc = new int[n + 1], low = new int[n + 1];
        boolean[] visited = new boolean[n + 1];
        int[] bridges = {0};
        int[] timer = {0};
        dfs(1, -1, adj, disc, low, visited, bridges, timer);
        return bridges[0];
    }

    private void dfs(int u, int par, List<List<Integer>> adj, int[] disc, int[] low,
                     boolean[] visited, int[] bridges, int[] timer) {
        visited[u] = true;
        disc[u] = low[u] = timer[0]++;
        for (int v : adj.get(u)) {
            if (!visited[v]) {
                dfs(v, u, adj, disc, low, visited, bridges, timer);
                low[u] = Math.min(low[u], low[v]);
                if (low[v] > disc[u]) bridges[0]++;
            } else if (v != par) {
                low[u] = Math.min(low[u], disc[v]);
            }
        }
    }

    public static void main(String[] args) {
        Problem09_RedundantConnectionBridge solver = new Problem09_RedundantConnectionBridge();

        // Tree: 1-2-3-4-5 with extra edge 1-4
        int[][] edges = {{1,2},{2,3},{3,4},{4,5},{1,4}};
        int[] redundant = solver.findRedundantConnection(edges);
        System.out.println("Redundant Connection (LeetCode 684)");
        System.out.println("Edges: " + Arrays.deepToString(edges));
        System.out.println("Redundant edge: " + Arrays.toString(redundant));
        
        int bridges = solver.countBridgesAfterRemoval(5, edges, redundant);
        System.out.println("Bridges after removal: " + bridges + " (tree has n-1=" + 4 + " bridges)");
        System.out.println("Result is a valid tree: " + (bridges == 4));

        // Example 2
        solver = new Problem09_RedundantConnectionBridge();
        int[][] edges2 = {{1,2},{1,3},{2,3}};
        int[] r2 = solver.findRedundantConnection(edges2);
        System.out.println("\nEdges: " + Arrays.deepToString(edges2));
        System.out.println("Redundant edge: " + Arrays.toString(r2));
    }
}
