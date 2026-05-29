import java.util.*;

/**
 * Problem 1: Articulation Points (Cut Vertices)
 * 
 * An articulation point is a vertex whose removal disconnects the graph.
 * 
 * Algorithm (Tarjan's):
 * - Root is an articulation point if it has 2+ children in DFS tree
 * - Non-root u is articulation point if it has a child v where low[v] >= disc[u]
 *   (meaning v cannot reach any ancestor of u without going through u)
 * 
 * Time: O(V + E)
 * 
 * Applications: Network vulnerability, finding critical routers
 */
public class Problem01_ArticulationPoints {

    private int timer = 0;

    public List<Integer> findArticulationPoints(int n, List<List<Integer>> adj) {
        int[] disc = new int[n], low = new int[n];
        boolean[] visited = new boolean[n], isAP = new boolean[n];
        Arrays.fill(disc, -1);

        for (int i = 0; i < n; i++) {
            if (!visited[i]) dfs(i, -1, adj, disc, low, visited, isAP);
        }

        List<Integer> result = new ArrayList<>();
        for (int i = 0; i < n; i++) if (isAP[i]) result.add(i);
        return result;
    }

    private void dfs(int u, int parent, List<List<Integer>> adj,
                     int[] disc, int[] low, boolean[] visited, boolean[] isAP) {
        visited[u] = true;
        disc[u] = low[u] = timer++;
        int children = 0;

        for (int v : adj.get(u)) {
            if (!visited[v]) {
                children++;
                dfs(v, u, adj, disc, low, visited, isAP);
                low[u] = Math.min(low[u], low[v]);

                // u is AP if:
                // 1. u is root and has 2+ children
                if (parent == -1 && children > 1) isAP[u] = true;
                // 2. u is not root and low[v] >= disc[u]
                if (parent != -1 && low[v] >= disc[u]) isAP[u] = true;
            } else if (v != parent) {
                low[u] = Math.min(low[u], disc[v]);
            }
        }
    }

    public static void main(String[] args) {
        Problem01_ArticulationPoints solver = new Problem01_ArticulationPoints();
        
        // Graph: 0-1-2-3 with 1-3 forming a bridge through 2
        int n = 5;
        List<List<Integer>> adj = new ArrayList<>();
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        int[][] edges = {{0,1},{1,2},{2,0},{1,3},{3,4}};
        for (int[] e : edges) { adj.get(e[0]).add(e[1]); adj.get(e[1]).add(e[0]); }

        List<Integer> aps = solver.findArticulationPoints(n, adj);
        System.out.println("Articulation Points (Cut Vertices)");
        System.out.println("Graph edges: " + Arrays.deepToString(edges));
        System.out.println("Articulation points: " + aps);
        // Expected: [1, 3] - removing 1 disconnects {0,2} from {3,4}
    }
}
