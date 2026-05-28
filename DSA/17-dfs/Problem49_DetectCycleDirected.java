import java.util.*;

/**
 * Problem: Detect Cycle in Directed Graph
 * Approach: DFS 3-color (white/gray/black) - gray->gray edge means cycle
 * Time: O(V+E), Space: O(V+E)
 * Production Analogy: Detecting deadlocks in directed task dependency graphs
 */
public class Problem49_DetectCycleDirected {
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
        for (int next : graph.get(node)) {
            if (color[next] == 1) return true;
            if (color[next] == 0 && dfs(graph, next, color)) return true;
        }
        color[node] = 2;
        return false;
    }

    public static void main(String[] args) {
        System.out.println(new Problem49_DetectCycleDirected().hasCycle(4, new int[][]{{0,1},{1,2},{2,0},{2,3}})); // true
        System.out.println(new Problem49_DetectCycleDirected().hasCycle(3, new int[][]{{0,1},{1,2}})); // false
    }
}
