import java.util.*;

/**
 * Problem: Critical Connections in a Network (LeetCode 1192)
 * Approach: Tarjan's bridge-finding algorithm - DFS with discovery/low times
 * Time: O(V+E), Space: O(V+E)
 * Production Analogy: Identifying single points of failure in network topology
 */
public class Problem24_CriticalConnections {
    int timer = 0;

    public List<List<Integer>> criticalConnections(int n, List<List<Integer>> connections) {
        List<List<Integer>> graph = new ArrayList<>(), res = new ArrayList<>();
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (List<Integer> c : connections) { graph.get(c.get(0)).add(c.get(1)); graph.get(c.get(1)).add(c.get(0)); }
        int[] disc = new int[n], low = new int[n];
        Arrays.fill(disc, -1);
        dfs(graph, 0, -1, disc, low, res);
        return res;
    }

    private void dfs(List<List<Integer>> graph, int u, int parent, int[] disc, int[] low, List<List<Integer>> res) {
        disc[u] = low[u] = timer++;
        for (int v : graph.get(u)) {
            if (v == parent) continue;
            if (disc[v] == -1) {
                dfs(graph, v, u, disc, low, res);
                low[u] = Math.min(low[u], low[v]);
                if (low[v] > disc[u]) res.add(Arrays.asList(u, v));
            } else {
                low[u] = Math.min(low[u], disc[v]);
            }
        }
    }

    public static void main(String[] args) {
        List<List<Integer>> conn = Arrays.asList(Arrays.asList(0,1),Arrays.asList(1,2),Arrays.asList(2,0),Arrays.asList(1,3));
        System.out.println(new Problem24_CriticalConnections().criticalConnections(4, conn));
    }
}
