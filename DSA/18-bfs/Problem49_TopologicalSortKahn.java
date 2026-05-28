import java.util.*;

/**
 * Problem: Topological Sort BFS (Kahn's Algorithm)
 * Approach: Repeatedly remove nodes with in-degree 0
 * Time: O(V+E), Space: O(V+E)
 * Production Analogy: Determining safe deployment order for interdependent services
 */
public class Problem49_TopologicalSortKahn {
    public int[] topologicalSort(int n, int[][] edges) {
        List<List<Integer>> graph = new ArrayList<>();
        int[] indegree = new int[n];
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] e : edges) { graph.get(e[0]).add(e[1]); indegree[e[1]]++; }
        Queue<Integer> q = new LinkedList<>();
        for (int i = 0; i < n; i++) if (indegree[i] == 0) q.offer(i);
        int[] order = new int[n];
        int idx = 0;
        while (!q.isEmpty()) {
            int node = q.poll();
            order[idx++] = node;
            for (int next : graph.get(node))
                if (--indegree[next] == 0) q.offer(next);
        }
        return idx == n ? order : new int[0]; // empty if cycle
    }

    public static void main(String[] args) {
        int[][] edges = {{5,2},{5,0},{4,0},{4,1},{2,3},{3,1}};
        System.out.println(Arrays.toString(new Problem49_TopologicalSortKahn().topologicalSort(6, edges)));
    }
}
