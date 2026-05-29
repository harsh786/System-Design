import java.util.*;

/**
 * Problem: Find Eventual Safe States
 * Find all nodes that eventually lead to terminal nodes (no outgoing edges).
 *
 * Approach: Reverse graph + topological sort from terminal nodes, or DFS with coloring
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Identifying safe execution paths in a workflow that always terminate.
 */
public class Problem05_FindEventualSafeStates {

    public List<Integer> eventualSafeNodes(int[][] graph) {
        int n = graph.length;
        int[] color = new int[n]; // 0=white, 1=gray, 2=black

        List<Integer> result = new ArrayList<>();
        for (int i = 0; i < n; i++)
            if (dfs(graph, i, color)) result.add(i);
        return result;
    }

    private boolean dfs(int[][] graph, int node, int[] color) {
        if (color[node] != 0) return color[node] == 2;
        color[node] = 1;
        for (int nei : graph[node])
            if (!dfs(graph, nei, color)) return false;
        color[node] = 2;
        return true;
    }

    public static void main(String[] args) {
        Problem05_FindEventualSafeStates solver = new Problem05_FindEventualSafeStates();
        int[][] graph = {{1,2},{2,3},{5},{0},{5},{},{}};
        System.out.println(solver.eventualSafeNodes(graph)); // [2,4,5,6]
    }
}
