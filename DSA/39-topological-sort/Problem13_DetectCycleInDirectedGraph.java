import java.util.*;

/**
 * Problem: Detect Cycle in Directed Graph
 *
 * Approach: DFS with 3 colors (white/gray/black) - cycle if we visit gray node
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V)
 *
 * Production Analogy: Detecting circular dependencies in package managers.
 */
public class Problem13_DetectCycleInDirectedGraph {

    public boolean hasCycle(int n, int[][] edges) {
        List<List<Integer>> graph = new ArrayList<>();
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] e : edges) graph.get(e[0]).add(e[1]);

        int[] color = new int[n];
        for (int i = 0; i < n; i++)
            if (color[i] == 0 && dfs(graph, i, color)) return true;
        return false;
    }

    private boolean dfs(List<List<Integer>> graph, int node, int[] color) {
        color[node] = 1;
        for (int nei : graph.get(node)) {
            if (color[nei] == 1) return true;
            if (color[nei] == 0 && dfs(graph, nei, color)) return true;
        }
        color[node] = 2;
        return false;
    }

    public static void main(String[] args) {
        Problem13_DetectCycleInDirectedGraph solver = new Problem13_DetectCycleInDirectedGraph();
        System.out.println(solver.hasCycle(3, new int[][]{{0,1},{1,2},{2,0}})); // true
        System.out.println(solver.hasCycle(3, new int[][]{{0,1},{1,2}})); // false
    }
}
