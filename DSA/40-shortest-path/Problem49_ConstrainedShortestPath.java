import java.util.*;

/**
 * Problem: Constrained Shortest Path
 * Shortest path with constraint (e.g., max total weight on secondary metric).
 *
 * Approach: Dijkstra with state (node, constraintUsed)
 *
 * Time Complexity: O((V*C + E*C) log(V*C))
 * Space Complexity: O(V * C)
 *
 * Production Analogy: Finding cheapest path within latency SLA budget.
 */
public class Problem49_ConstrainedShortestPath {

    public int shortestPath(int n, int[][] edges, int src, int dst, int maxConstraint) {
        // edges: [u, v, cost, constraintCost]
        List<int[]>[] graph = new List[n];
        for (int i = 0; i < n; i++) graph[i] = new ArrayList<>();
        for (int[] e : edges) { graph[e[0]].add(new int[]{e[1], e[2], e[3]}); graph[e[1]].add(new int[]{e[0], e[2], e[3]}); }

        int[][] dist = new int[n][maxConstraint + 1];
        for (int[] row : dist) Arrays.fill(row, Integer.MAX_VALUE);
        dist[src][0] = 0;

        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[2] - b[2]);
        pq.offer(new int[]{src, 0, 0}); // node, constraintUsed, cost

        while (!pq.isEmpty()) {
            int[] cur = pq.poll();
            int u = cur[0], cUsed = cur[1], cost = cur[2];
            if (u == dst) return cost;
            if (cost > dist[u][cUsed]) continue;
            for (int[] nei : graph[u]) {
                int nc = cUsed + nei[2];
                if (nc <= maxConstraint && cost + nei[1] < dist[nei[0]][nc]) {
                    dist[nei[0]][nc] = cost + nei[1];
                    pq.offer(new int[]{nei[0], nc, dist[nei[0]][nc]});
                }
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        Problem49_ConstrainedShortestPath solver = new Problem49_ConstrainedShortestPath();
        // edges: [u, v, cost, constraintCost]
        int[][] edges = {{0,1,2,3},{0,2,5,1},{1,2,1,2},{1,3,6,1},{2,3,2,2}};
        System.out.println(solver.shortestPath(4, edges, 0, 3, 4)); // cheapest within constraint
    }
}
