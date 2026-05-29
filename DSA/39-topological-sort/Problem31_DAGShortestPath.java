import java.util.*;

/**
 * Problem: DAG Shortest Path
 * Find shortest path from source to all vertices in a weighted DAG.
 *
 * Approach: Topological sort then relax edges in order
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Finding minimum-cost execution path through a pipeline.
 */
public class Problem31_DAGShortestPath {

    public int[] shortestPath(int n, int[][] edges, int src) {
        List<int[]>[] graph = new List[n];
        for (int i = 0; i < n; i++) graph[i] = new ArrayList<>();
        int[] inDeg = new int[n];
        for (int[] e : edges) { graph[e[0]].add(new int[]{e[1], e[2]}); inDeg[e[1]]++; }

        // Topological sort
        Queue<Integer> q = new LinkedList<>();
        for (int i = 0; i < n; i++) if (inDeg[i] == 0) q.offer(i);
        List<Integer> order = new ArrayList<>();
        while (!q.isEmpty()) {
            int node = q.poll(); order.add(node);
            for (int[] nei : graph[node]) if (--inDeg[nei[0]] == 0) q.offer(nei[0]);
        }

        int[] dist = new int[n];
        Arrays.fill(dist, Integer.MAX_VALUE);
        dist[src] = 0;
        for (int node : order) {
            if (dist[node] == Integer.MAX_VALUE) continue;
            for (int[] nei : graph[node])
                dist[nei[0]] = Math.min(dist[nei[0]], dist[node] + nei[1]);
        }
        return dist;
    }

    public static void main(String[] args) {
        Problem31_DAGShortestPath solver = new Problem31_DAGShortestPath();
        int[][] edges = {{0,1,2},{0,2,4},{1,2,1},{1,3,7},{2,4,3},{3,4,1}};
        System.out.println(Arrays.toString(solver.shortestPath(5, edges, 0)));
    }
}
