import java.util.*;

/**
 * Problem 15: Find Eventual Safe States (LeetCode 802)
 * 
 * Approach: Reverse topological sort. Nodes not in cycles are safe. Use coloring (DFS).
 * Time: O(V + E), Space: O(V + E)
 * 
 * Production Analogy: Identifying services that always terminate (no circular async calls).
 */
public class Problem15_FindEventualSafeStates {
    
    public List<Integer> eventualSafeNodes(int[][] graph) {
        int n = graph.length;
        int[] color = new int[n]; // 0=white, 1=gray, 2=black
        List<Integer> result = new ArrayList<>();
        for (int i = 0; i < n; i++)
            if (dfs(graph, i, color)) result.add(i);
        return result;
    }
    
    boolean dfs(int[][] graph, int node, int[] color) {
        if (color[node] != 0) return color[node] == 2;
        color[node] = 1;
        for (int next : graph[node])
            if (!dfs(graph, next, color)) return false;
        color[node] = 2;
        return true;
    }
    
    public static void main(String[] args) {
        Problem15_FindEventualSafeStates sol = new Problem15_FindEventualSafeStates();
        System.out.println(sol.eventualSafeNodes(new int[][]{{1,2},{2,3},{5},{0},{5},{},{}})); // [2,4,5,6]
        System.out.println(sol.eventualSafeNodes(new int[][]{{1,2,3,4},{1,2},{3,4},{0,4},{}})); // [4]
    }
}
