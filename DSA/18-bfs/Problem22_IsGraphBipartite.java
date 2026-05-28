import java.util.*;

/**
 * Problem: Is Graph Bipartite (LeetCode 785)
 * Approach: BFS coloring - alternate colors, if neighbor has same color => not bipartite
 * Time: O(V+E), Space: O(V)
 * Production Analogy: Two-tier resource allocation without conflicts (e.g., separating readers/writers)
 */
public class Problem22_IsGraphBipartite {
    public boolean isBipartite(int[][] graph) {
        int n = graph.length;
        int[] color = new int[n]; // 0=uncolored, 1, -1
        for (int i = 0; i < n; i++) {
            if (color[i] != 0) continue;
            Queue<Integer> q = new LinkedList<>();
            q.offer(i); color[i] = 1;
            while (!q.isEmpty()) {
                int node = q.poll();
                for (int next : graph[node]) {
                    if (color[next] == 0) { color[next] = -color[node]; q.offer(next); }
                    else if (color[next] == color[node]) return false;
                }
            }
        }
        return true;
    }

    public static void main(String[] args) {
        int[][] graph = {{1,3},{0,2},{1,3},{0,2}};
        System.out.println(new Problem22_IsGraphBipartite().isBipartite(graph)); // true
    }
}
