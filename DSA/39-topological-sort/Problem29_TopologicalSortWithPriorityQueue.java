import java.util.*;

/**
 * Problem: Topological Sort with Priority Queue
 * Generate topological order respecting priority (largest/smallest first).
 *
 * Approach: Kahn's algorithm with PriorityQueue instead of Queue
 *
 * Time Complexity: O((V + E) log V)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Scheduling high-priority tasks first among equally-ready tasks.
 */
public class Problem29_TopologicalSortWithPriorityQueue {

    public List<Integer> topSortMaxFirst(int n, int[][] edges) {
        List<List<Integer>> graph = new ArrayList<>();
        int[] inDeg = new int[n];
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] e : edges) { graph.get(e[0]).add(e[1]); inDeg[e[1]]++; }

        PriorityQueue<Integer> pq = new PriorityQueue<>(Collections.reverseOrder());
        for (int i = 0; i < n; i++) if (inDeg[i] == 0) pq.offer(i);

        List<Integer> result = new ArrayList<>();
        while (!pq.isEmpty()) {
            int node = pq.poll(); result.add(node);
            for (int nei : graph.get(node)) if (--inDeg[nei] == 0) pq.offer(nei);
        }
        return result;
    }

    public static void main(String[] args) {
        Problem29_TopologicalSortWithPriorityQueue solver = new Problem29_TopologicalSortWithPriorityQueue();
        System.out.println(solver.topSortMaxFirst(5, new int[][]{{0,1},{2,1},{3,4}}));
    }
}
