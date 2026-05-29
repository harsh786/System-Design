import java.util.*;

/**
 * Problem 2: Bridges in a Graph
 * 
 * A bridge is an edge whose removal increases the number of connected components.
 * 
 * Algorithm: Similar to articulation points.
 * Edge (u,v) is a bridge if low[v] > disc[u]
 * (strict inequality - unlike articulation points which use >=)
 * 
 * If low[v] == disc[u], there's a back edge from v's subtree to u,
 * so removing (u,v) doesn't disconnect.
 * 
 * Time: O(V + E)
 */
public class Problem02_Bridges {

    private int timer = 0;

    public List<int[]> findBridges(int n, List<List<Integer>> adj) {
        int[] disc = new int[n], low = new int[n];
        boolean[] visited = new boolean[n];
        List<int[]> bridges = new ArrayList<>();

        for (int i = 0; i < n; i++) {
            if (!visited[i]) dfs(i, -1, adj, disc, low, visited, bridges);
        }
        return bridges;
    }

    private void dfs(int u, int parent, List<List<Integer>> adj,
                     int[] disc, int[] low, boolean[] visited, List<int[]> bridges) {
        visited[u] = true;
        disc[u] = low[u] = timer++;

        for (int v : adj.get(u)) {
            if (!visited[v]) {
                dfs(v, u, adj, disc, low, visited, bridges);
                low[u] = Math.min(low[u], low[v]);
                // Bridge: v's subtree cannot reach u or above without (u,v)
                if (low[v] > disc[u]) {
                    bridges.add(new int[]{u, v});
                }
            } else if (v != parent) {
                low[u] = Math.min(low[u], disc[v]);
            }
        }
    }

    public static void main(String[] args) {
        Problem02_Bridges solver = new Problem02_Bridges();

        int n = 7;
        List<List<Integer>> adj = new ArrayList<>();
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        // Two triangles connected by a bridge
        int[][] edges = {{0,1},{1,2},{2,0},{2,3},{3,4},{4,5},{5,6},{6,3}};
        for (int[] e : edges) { adj.get(e[0]).add(e[1]); adj.get(e[1]).add(e[0]); }

        List<int[]> bridges = solver.findBridges(n, adj);
        System.out.println("Bridges in Graph");
        System.out.println("Edges: " + Arrays.deepToString(edges));
        System.out.print("Bridges: ");
        for (int[] b : bridges) System.out.print(Arrays.toString(b) + " ");
        System.out.println();
        // Expected: [2, 3] - the bridge connecting two triangles
    }
}
