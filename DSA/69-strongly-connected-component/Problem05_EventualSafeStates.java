import java.util.*;

/**
 * Problem 5: Find Eventual Safe States (LeetCode 802)
 * 
 * A node is "safe" if every path from it leads to a terminal node (out-degree 0).
 * Equivalently, a node is safe if it's NOT part of any cycle.
 * 
 * Approach 1: Topological sort (reverse BFS from terminal nodes)
 * Approach 2: DFS with coloring (detect cycle membership)
 * Approach 3: SCC-based (nodes in non-trivial SCCs are unsafe)
 * 
 * Time: O(V + E)
 */
public class Problem05_EventualSafeStates {

    // Approach 1: DFS coloring (most elegant)
    // WHITE=0: unvisited, GRAY=1: in current DFS path, BLACK=2: safe
    public static List<Integer> eventualSafeNodes(int[][] graph) {
        int n = graph.length;
        int[] color = new int[n]; // 0=white, 1=gray, 2=black
        List<Integer> result = new ArrayList<>();
        
        for (int i = 0; i < n; i++) {
            if (dfs(i, graph, color)) {
                result.add(i);
            }
        }
        return result;
    }

    // Returns true if node is safe (no cycle reachable)
    private static boolean dfs(int u, int[][] graph, int[] color) {
        if (color[u] != 0) return color[u] == 2; // Already processed
        
        color[u] = 1; // Mark as in-progress (gray)
        for (int v : graph[u]) {
            if (color[v] == 1 || !dfs(v, graph, color)) {
                return false; // Cycle found
            }
        }
        color[u] = 2; // Safe (black)
        return true;
    }

    // Approach 2: Reverse topological sort (BFS)
    public static List<Integer> eventualSafeNodesBFS(int[][] graph) {
        int n = graph.length;
        // Build reverse graph and track out-degree
        List<List<Integer>> reverseGraph = new ArrayList<>();
        for (int i = 0; i < n; i++) reverseGraph.add(new ArrayList<>());
        int[] outDegree = new int[n];
        
        for (int u = 0; u < n; u++) {
            outDegree[u] = graph[u].length;
            for (int v : graph[u]) {
                reverseGraph.get(v).add(u);
            }
        }
        
        // Start BFS from terminal nodes (out-degree 0)
        Queue<Integer> queue = new LinkedList<>();
        for (int i = 0; i < n; i++) {
            if (outDegree[i] == 0) queue.offer(i);
        }
        
        boolean[] safe = new boolean[n];
        while (!queue.isEmpty()) {
            int u = queue.poll();
            safe[u] = true;
            for (int v : reverseGraph.get(u)) {
                outDegree[v]--;
                if (outDegree[v] == 0) queue.offer(v);
            }
        }
        
        List<Integer> result = new ArrayList<>();
        for (int i = 0; i < n; i++) if (safe[i]) result.add(i);
        return result;
    }

    public static void main(String[] args) {
        int[][] graph = {{1,2},{2,3},{5},{0},{5},{},{}};
        // Node 5,6 are terminal. Node 2->5, Node 4->5 safe.
        // Node 0->1->2->5, 0->2->5 safe. Node 3->0 creates cycle with 0->1->2->...
        
        System.out.println("LeetCode 802: Find Eventual Safe States");
        System.out.println("DFS approach: " + eventualSafeNodes(graph));
        System.out.println("BFS approach: " + eventualSafeNodesBFS(graph));
        // Expected: [2, 4, 5, 6]
    }
}
