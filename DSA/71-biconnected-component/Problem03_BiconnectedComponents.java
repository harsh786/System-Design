import java.util.*;

/**
 * Problem 3: Biconnected Components
 * 
 * A biconnected component is a maximal biconnected subgraph.
 * A graph is biconnected if it's connected and has no articulation points
 * (removing any single vertex keeps it connected).
 * 
 * Properties:
 * - Every edge belongs to exactly one biconnected component
 * - Two biconnected components share at most one vertex (an articulation point)
 * - A biconnected component with 3+ vertices has no bridges
 * 
 * Algorithm: DFS with edge stack. When we identify an articulation point
 * (low[v] >= disc[u]), pop edges from stack to form a component.
 */
public class Problem03_BiconnectedComponents {

    private int timer = 0;

    public List<List<int[]>> findBiconnectedComponents(int n, List<List<int[]>> adj) {
        // adj[u] contains [v, edgeId]
        int[] disc = new int[n], low = new int[n];
        boolean[] visited = new boolean[n];
        Deque<int[]> edgeStack = new ArrayDeque<>();
        List<List<int[]>> components = new ArrayList<>();

        for (int i = 0; i < n; i++) {
            if (!visited[i]) dfs(i, -1, adj, disc, low, visited, edgeStack, components);
            // Remaining edges on stack form a component
            if (!edgeStack.isEmpty()) {
                components.add(new ArrayList<>(edgeStack));
                edgeStack.clear();
            }
        }
        return components;
    }

    private void dfs(int u, int parent, List<List<int[]>> adj, int[] disc, int[] low,
                     boolean[] visited, Deque<int[]> edgeStack, List<List<int[]>> components) {
        visited[u] = true;
        disc[u] = low[u] = timer++;
        int children = 0;

        for (int[] edge : adj.get(u)) {
            int v = edge[0];
            if (!visited[v]) {
                children++;
                edgeStack.push(new int[]{u, v});
                dfs(v, u, adj, disc, low, visited, edgeStack, components);
                low[u] = Math.min(low[u], low[v]);

                // If u is an articulation point, pop component
                boolean isAP = (parent == -1 && children > 1) || (parent != -1 && low[v] >= disc[u]);
                if (isAP) {
                    List<int[]> component = new ArrayList<>();
                    while (!edgeStack.isEmpty()) {
                        int[] top = edgeStack.peek();
                        if (top[0] == u && top[1] == v) {
                            component.add(edgeStack.pop());
                            break;
                        }
                        component.add(edgeStack.pop());
                    }
                    components.add(component);
                }
            } else if (v != parent && disc[v] < disc[u]) {
                edgeStack.push(new int[]{u, v});
                low[u] = Math.min(low[u], disc[v]);
            }
        }
    }

    public static void main(String[] args) {
        int n = 6;
        List<List<int[]>> adj = new ArrayList<>();
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        
        int[][] edges = {{0,1},{1,2},{2,0},{1,3},{3,4},{4,5},{5,3}};
        for (int[] e : edges) {
            adj.get(e[0]).add(new int[]{e[1], 0});
            adj.get(e[1]).add(new int[]{e[0], 0});
        }

        Problem03_BiconnectedComponents solver = new Problem03_BiconnectedComponents();
        List<List<int[]>> components = solver.findBiconnectedComponents(n, adj);

        System.out.println("Biconnected Components");
        System.out.println("Edges: " + Arrays.deepToString(edges));
        System.out.println("Number of biconnected components: " + components.size());
        for (int i = 0; i < components.size(); i++) {
            System.out.print("  Component " + i + ": ");
            for (int[] e : components.get(i)) System.out.print("(" + e[0] + "-" + e[1] + ") ");
            System.out.println();
        }
    }
}
