import java.util.*;

/**
 * Problem: Critical Path in DAG
 * Find the longest path (critical path) in a weighted DAG.
 *
 * Approach: Topological sort + DP to compute longest distances
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Identifying the bottleneck path in a project schedule (CPM).
 */
public class Problem17_CriticalPathInDAG {

    public int criticalPath(int n, int[] durations, int[][] deps) {
        List<List<Integer>> graph = new ArrayList<>();
        int[] inDeg = new int[n];
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] d : deps) { graph.get(d[0]).add(d[1]); inDeg[d[1]]++; }

        int[] dist = new int[n];
        Queue<Integer> q = new LinkedList<>();
        for (int i = 0; i < n; i++) {
            dist[i] = durations[i];
            if (inDeg[i] == 0) q.offer(i);
        }

        while (!q.isEmpty()) {
            int node = q.poll();
            for (int nei : graph.get(node)) {
                dist[nei] = Math.max(dist[nei], dist[node] + durations[nei]);
                if (--inDeg[nei] == 0) q.offer(nei);
            }
        }

        int max = 0;
        for (int d : dist) max = Math.max(max, d);
        return max;
    }

    public static void main(String[] args) {
        Problem17_CriticalPathInDAG solver = new Problem17_CriticalPathInDAG();
        System.out.println(solver.criticalPath(4, new int[]{3,2,4,1}, new int[][]{{0,1},{0,2},{1,3},{2,3}})); // 8
    }
}
