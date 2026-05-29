import java.util.*;

/**
 * Problem: Kahn's Algorithm (BFS Topological Sort)
 * Classic implementation of BFS-based topological sort.
 *
 * Approach: Repeatedly remove nodes with in-degree 0
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Task queue processing where tasks become available as dependencies complete.
 */
public class Problem14_KahnsAlgorithm {

    public List<Integer> topologicalSort(int n, int[][] edges) {
        List<List<Integer>> graph = new ArrayList<>();
        int[] inDeg = new int[n];
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] e : edges) { graph.get(e[0]).add(e[1]); inDeg[e[1]]++; }

        Queue<Integer> q = new LinkedList<>();
        for (int i = 0; i < n; i++) if (inDeg[i] == 0) q.offer(i);

        List<Integer> order = new ArrayList<>();
        while (!q.isEmpty()) {
            int node = q.poll();
            order.add(node);
            for (int nei : graph.get(node))
                if (--inDeg[nei] == 0) q.offer(nei);
        }
        return order.size() == n ? order : Collections.emptyList();
    }

    public static void main(String[] args) {
        Problem14_KahnsAlgorithm solver = new Problem14_KahnsAlgorithm();
        System.out.println(solver.topologicalSort(6, new int[][]{{5,2},{5,0},{4,0},{4,1},{2,3},{3,1}}));
    }
}
