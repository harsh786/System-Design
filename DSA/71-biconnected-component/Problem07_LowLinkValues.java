import java.util.*;

/**
 * Problem 7: Low-Link Values (Tarjan's DFS Framework)
 * 
 * Low-link values are the foundation for:
 * - Finding SCCs (directed graphs)
 * - Finding articulation points (undirected graphs)
 * - Finding bridges (undirected graphs)
 * - Finding biconnected components
 * 
 * Definition: low[u] = min(disc[u], disc[w]) for all w reachable from u
 * through one back edge in the subtree rooted at u.
 * 
 * This visualizes the DFS tree, discovery times, and low-link values.
 */
public class Problem07_LowLinkValues {

    private int timer = 0;

    public void analyzeLowLinks(int n, List<List<Integer>> adj) {
        int[] disc = new int[n], low = new int[n], parent = new int[n];
        boolean[] visited = new boolean[n];
        Arrays.fill(parent, -1);
        List<String> treeEdges = new ArrayList<>();
        List<String> backEdges = new ArrayList<>();

        for (int i = 0; i < n; i++) {
            if (!visited[i]) dfs(i, adj, disc, low, visited, parent, treeEdges, backEdges);
        }

        System.out.println("DFS Analysis with Low-Link Values");
        System.out.println("==================================\n");
        
        System.out.printf("%-8s %-8s %-8s %-8s%n", "Vertex", "disc[]", "low[]", "Parent");
        for (int i = 0; i < n; i++) {
            System.out.printf("%-8d %-8d %-8d %-8s%n", i, disc[i], low[i],
                parent[i] == -1 ? "root" : String.valueOf(parent[i]));
        }
        
        System.out.println("\nTree edges: " + treeEdges);
        System.out.println("Back edges: " + backEdges);
        
        // Identify structures
        System.out.println("\nBridges (low[v] > disc[u]):");
        for (int u = 0; u < n; u++) {
            for (int v : adj.get(u)) {
                if (parent[v] == u && low[v] > disc[u]) {
                    System.out.println("  Edge (" + u + ", " + v + ")");
                }
            }
        }
        
        System.out.println("\nArticulation points:");
        for (int u = 0; u < n; u++) {
            if (parent[u] == -1) {
                // Root: check children count
                int children = 0;
                for (int v : adj.get(u)) if (parent[v] == u) children++;
                if (children > 1) System.out.println("  Vertex " + u + " (root with " + children + " children)");
            } else {
                for (int v : adj.get(u)) {
                    if (parent[v] == u && low[v] >= disc[u]) {
                        System.out.println("  Vertex " + u + " (low[" + v + "]=" + low[v] + " >= disc[" + u + "]=" + disc[u] + ")");
                        break;
                    }
                }
            }
        }
    }

    private void dfs(int u, List<List<Integer>> adj, int[] disc, int[] low,
                     boolean[] visited, int[] parent, List<String> tree, List<String> back) {
        visited[u] = true;
        disc[u] = low[u] = timer++;

        for (int v : adj.get(u)) {
            if (!visited[v]) {
                parent[v] = u;
                tree.add(u + "->" + v);
                dfs(v, adj, disc, low, visited, parent, tree, back);
                low[u] = Math.min(low[u], low[v]);
            } else if (v != parent[u]) {
                back.add(u + "->" + v);
                low[u] = Math.min(low[u], disc[v]);
            }
        }
    }

    public static void main(String[] args) {
        int n = 6;
        List<List<Integer>> adj = new ArrayList<>();
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        int[][] edges = {{0,1},{1,2},{2,0},{1,3},{3,4},{4,5},{5,3}};
        for (int[] e : edges) { adj.get(e[0]).add(e[1]); adj.get(e[1]).add(e[0]); }

        new Problem07_LowLinkValues().analyzeLowLinks(n, adj);
    }
}
