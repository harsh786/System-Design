import java.util.*;

/**
 * Problem: DAG Longest Path
 * Find longest path from source in a weighted DAG.
 *
 * Approach: Topological sort, negate weights or use max relaxation
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Finding the critical path / maximum latency path in a pipeline.
 */
public class Problem32_DAGLongestPath {

    public int[] longestPath(int n, int[][] edges, int src) {
        List<int[]>[] graph = new List[n];
        for (int i = 0; i < n; i++) graph[i] = new ArrayList<>();
        int[] inDeg = new int[n];
        for (int[] e : edges) { graph[e[0]].add(new int[]{e[1], e[2]}); inDeg[e[1]]++; }

        Queue<Integer> q = new LinkedList<>();
        for (int i = 0; i < n; i++) if (inDeg[i] == 0) q.offer(i);
        List<Integer> order = new ArrayList<>();
        while (!q.isEmpty()) {
            int node = q.poll(); order.add(node);
            for (int[] nei : graph[node]) if (--inDeg[nei[0]] == 0) q.offer(nei[0]);
        }

        int[] dist = new int[n];
        Arrays.fill(dist, Integer.MIN_VALUE);
        dist[src] = 0;
        for (int node : order) {
            if (dist[node] == Integer.MIN_VALUE) continue;
            for (int[] nei : graph[node])
                dist[nei[0]] = Math.max(dist[nei[0]], dist[node] + nei[1]);
        }
        return dist;
    }

    public static void main(String[] args) {
        Problem32_DAGLongestPath solver = new Problem32_DAGLongestPath();
        int[][] edges = {{0,1,2},{0,2,4},{1,3,3},{2,3,1},{3,4,5}};
        System.out.println(Arrays.toString(solver.longestPath(5, edges, 0)));
    }
}
