import java.util.*;

/**
 * Problem: Detect Cycle in Undirected Graph
 * Approach: DFS - if we visit an already-visited node that isn't parent, cycle exists
 * Time: O(V+E), Space: O(V+E)
 * Production Analogy: Detecting circular references in bidirectional service dependencies
 */
public class Problem48_DetectCycleUndirected {
    public boolean hasCycle(int n, int[][] edges) {
        List<List<Integer>> graph = new ArrayList<>();
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] e : edges) { graph.get(e[0]).add(e[1]); graph.get(e[1]).add(e[0]); }
        boolean[] visited = new boolean[n];
        for (int i = 0; i < n; i++)
            if (!visited[i] && dfs(graph, i, -1, visited)) return true;
        return false;
    }

    private boolean dfs(List<List<Integer>> graph, int node, int parent, boolean[] visited) {
        visited[node] = true;
        for (int next : graph.get(node)) {
            if (!visited[next]) { if (dfs(graph, next, node, visited)) return true; }
            else if (next != parent) return true;
        }
        return false;
    }

    public static void main(String[] args) {
        System.out.println(new Problem48_DetectCycleUndirected().hasCycle(4, new int[][]{{0,1},{1,2},{2,0},{2,3}})); // true
        System.out.println(new Problem48_DetectCycleUndirected().hasCycle(3, new int[][]{{0,1},{1,2}})); // false
    }
}
