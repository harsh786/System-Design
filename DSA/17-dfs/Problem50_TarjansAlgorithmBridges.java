import java.util.*;

/**
 * Problem: Tarjan's Algorithm for Bridges
 * Approach: DFS tracking discovery time and low-link values; bridge if low[v] > disc[u]
 * Time: O(V+E), Space: O(V+E)
 * Production Analogy: Finding single points of failure whose removal disconnects the network
 */
public class Problem50_TarjansAlgorithmBridges {
    int timer = 0;

    public List<int[]> findBridges(int n, int[][] edges) {
        List<List<Integer>> graph = new ArrayList<>();
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] e : edges) { graph.get(e[0]).add(e[1]); graph.get(e[1]).add(e[0]); }

        int[] disc = new int[n], low = new int[n];
        boolean[] visited = new boolean[n];
        List<int[]> bridges = new ArrayList<>();
        for (int i = 0; i < n; i++)
            if (!visited[i]) dfs(graph, i, -1, disc, low, visited, bridges);
        return bridges;
    }

    private void dfs(List<List<Integer>> graph, int u, int parent, int[] disc, int[] low, boolean[] visited, List<int[]> bridges) {
        visited[u] = true;
        disc[u] = low[u] = timer++;
        for (int v : graph.get(u)) {
            if (v == parent) continue;
            if (!visited[v]) {
                dfs(graph, v, u, disc, low, visited, bridges);
                low[u] = Math.min(low[u], low[v]);
                if (low[v] > disc[u]) bridges.add(new int[]{u, v});
            } else {
                low[u] = Math.min(low[u], disc[v]);
            }
        }
    }

    public static void main(String[] args) {
        int[][] edges = {{0,1},{1,2},{2,0},{1,3},{3,4},{4,5},{5,3}};
        List<int[]> bridges = new Problem50_TarjansAlgorithmBridges().findBridges(6, edges);
        for (int[] b : bridges) System.out.println(Arrays.toString(b)); // [1, 3]
    }
}
