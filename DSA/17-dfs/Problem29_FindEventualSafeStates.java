import java.util.*;

/**
 * Problem: Find Eventual Safe States (LeetCode 802)
 * Approach: DFS 3-color - node is safe if all paths from it lead to terminal nodes (no cycles)
 * Time: O(V+E), Space: O(V)
 * Production Analogy: Identifying services guaranteed to complete without deadlock
 */
public class Problem29_FindEventualSafeStates {
    public List<Integer> eventualSafeNodes(int[][] graph) {
        int n = graph.length;
        int[] color = new int[n]; // 0=unvisited, 1=visiting, 2=safe
        List<Integer> res = new ArrayList<>();
        for (int i = 0; i < n; i++)
            if (isSafe(graph, i, color)) res.add(i);
        return res;
    }

    private boolean isSafe(int[][] graph, int node, int[] color) {
        if (color[node] > 0) return color[node] == 2;
        color[node] = 1;
        for (int next : graph[node])
            if (!isSafe(graph, next, color)) return false;
        color[node] = 2;
        return true;
    }

    public static void main(String[] args) {
        int[][] graph = {{1,2},{2,3},{5},{0},{5},{},{}};
        System.out.println(new Problem29_FindEventualSafeStates().eventualSafeNodes(graph));
    }
}
