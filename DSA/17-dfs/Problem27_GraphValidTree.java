import java.util.*;

/**
 * Problem: Graph Valid Tree (LeetCode 261)
 * Approach: DFS - valid tree = connected + no cycles (V-1 edges + all connected)
 * Time: O(V+E), Space: O(V+E)
 * Production Analogy: Validating a service hierarchy has no circular dependencies and is fully connected
 */
public class Problem27_GraphValidTree {
    public boolean validTree(int n, int[][] edges) {
        if (edges.length != n - 1) return false;
        List<List<Integer>> graph = new ArrayList<>();
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] e : edges) { graph.get(e[0]).add(e[1]); graph.get(e[1]).add(e[0]); }
        boolean[] visited = new boolean[n];
        dfs(graph, 0, visited);
        for (boolean v : visited) if (!v) return false;
        return true;
    }

    private void dfs(List<List<Integer>> graph, int node, boolean[] visited) {
        visited[node] = true;
        for (int next : graph.get(node))
            if (!visited[next]) dfs(graph, next, visited);
    }

    public static void main(String[] args) {
        System.out.println(new Problem27_GraphValidTree().validTree(5, new int[][]{{0,1},{0,2},{0,3},{1,4}})); // true
        System.out.println(new Problem27_GraphValidTree().validTree(5, new int[][]{{0,1},{1,2},{2,3},{1,3},{1,4}})); // false
    }
}
