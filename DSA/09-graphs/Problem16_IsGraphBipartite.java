import java.util.*;

/**
 * Problem 16: Is Graph Bipartite (LeetCode 785)
 * 
 * Approach: BFS coloring. Assign colors alternately; if conflict found, not bipartite.
 * Time: O(V + E), Space: O(V)
 * 
 * Production Analogy: Assigning tasks to two worker pools with conflict constraints.
 */
public class Problem16_IsGraphBipartite {
    
    public boolean isBipartite(int[][] graph) {
        int n = graph.length;
        int[] color = new int[n]; // 0=uncolored, 1, -1
        for (int i = 0; i < n; i++) {
            if (color[i] != 0) continue;
            Queue<Integer> q = new LinkedList<>();
            q.offer(i); color[i] = 1;
            while (!q.isEmpty()) {
                int node = q.poll();
                for (int nei : graph[node]) {
                    if (color[nei] == 0) { color[nei] = -color[node]; q.offer(nei); }
                    else if (color[nei] == color[node]) return false;
                }
            }
        }
        return true;
    }
    
    public static void main(String[] args) {
        Problem16_IsGraphBipartite sol = new Problem16_IsGraphBipartite();
        System.out.println(sol.isBipartite(new int[][]{{1,2,3},{0,2},{0,1,3},{0,2}})); // false
        System.out.println(sol.isBipartite(new int[][]{{1,3},{0,2},{1,3},{0,2}})); // true
    }
}
