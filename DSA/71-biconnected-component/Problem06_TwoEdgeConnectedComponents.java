import java.util.*;

/**
 * Problem 6: Two-Edge-Connected Components
 * 
 * A graph is 2-edge-connected if it remains connected after removing any single edge.
 * 2-edge-connected components are maximal 2-edge-connected subgraphs.
 * 
 * Two vertices are in the same 2-edge-connected component iff every edge on
 * the path between them is NOT a bridge.
 * 
 * Algorithm:
 * 1. Find all bridges
 * 2. Remove bridges; remaining connected components are 2-edge-connected components
 * (Or: contract bridges and use DFS)
 * 
 * Time: O(V + E)
 */
public class Problem06_TwoEdgeConnectedComponents {

    private int timer = 0;

    public List<List<Integer>> findTwoEdgeComponents(int n, List<List<int[]>> adj) {
        // adj[u] contains [v, edgeIndex]
        int[] disc = new int[n], low = new int[n], comp = new int[n];
        boolean[] visited = new boolean[n];
        Set<Integer> bridgeEdges = new HashSet<>();
        Arrays.fill(comp, -1);

        // Step 1: Find bridges
        for (int i = 0; i < n; i++) {
            if (!visited[i]) dfsBridges(i, -1, adj, disc, low, visited, bridgeEdges);
        }

        // Step 2: DFS ignoring bridge edges to find components
        Arrays.fill(visited, false);
        List<List<Integer>> components = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            if (!visited[i]) {
                List<Integer> component = new ArrayList<>();
                dfsComponent(i, adj, visited, bridgeEdges, component);
                components.add(component);
            }
        }
        return components;
    }

    private void dfsBridges(int u, int parentEdge, List<List<int[]>> adj,
                            int[] disc, int[] low, boolean[] visited, Set<Integer> bridges) {
        visited[u] = true;
        disc[u] = low[u] = timer++;
        for (int[] edge : adj.get(u)) {
            int v = edge[0], edgeIdx = edge[1];
            if (edgeIdx == parentEdge) continue;
            if (!visited[v]) {
                dfsBridges(v, edgeIdx, adj, disc, low, visited, bridges);
                low[u] = Math.min(low[u], low[v]);
                if (low[v] > disc[u]) bridges.add(edgeIdx);
            } else {
                low[u] = Math.min(low[u], disc[v]);
            }
        }
    }

    private void dfsComponent(int u, List<List<int[]>> adj, boolean[] visited,
                              Set<Integer> bridges, List<Integer> component) {
        visited[u] = true;
        component.add(u);
        for (int[] edge : adj.get(u)) {
            if (!visited[edge[0]] && !bridges.contains(edge[1])) {
                dfsComponent(edge[0], adj, visited, bridges, component);
            }
        }
    }

    public static void main(String[] args) {
        int n = 7;
        List<List<int[]>> adj = new ArrayList<>();
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        // Triangle + bridge + square
        int[][] edges = {{0,1},{1,2},{2,0},{2,3},{3,4},{4,5},{5,6},{6,3}};
        for (int i = 0; i < edges.length; i++) {
            adj.get(edges[i][0]).add(new int[]{edges[i][1], i});
            adj.get(edges[i][1]).add(new int[]{edges[i][0], i});
        }

        Problem06_TwoEdgeConnectedComponents solver = new Problem06_TwoEdgeConnectedComponents();
        List<List<Integer>> comps = solver.findTwoEdgeComponents(n, adj);

        System.out.println("Two-Edge-Connected Components");
        System.out.println("Edges: " + Arrays.deepToString(edges));
        System.out.println("Components: " + comps);
        // Expected: {0,1,2} and {3,4,5,6} with bridge (2,3)
    }
}
