import java.util.*;

/**
 * Problem: Johnson's Algorithm
 * All-pairs shortest path for sparse graphs (handles negative weights).
 *
 * Approach: Bellman-Ford for reweighting + Dijkstra from each node
 *
 * Time Complexity: O(V * (V + E) log V)
 * Space Complexity: O(V^2)
 *
 * Production Analogy: Computing all-pairs latency in a heterogeneous network.
 */
public class Problem37_JohnsonsAlgorithm {

    public int[][] johnson(int n, int[][] edges) {
        // Add virtual node connected to all with weight 0
        int[][] augEdges = new int[edges.length + n][3];
        System.arraycopy(edges, 0, augEdges, 0, edges.length);
        for (int i = 0; i < n; i++) augEdges[edges.length + i] = new int[]{n, i, 0};

        // Bellman-Ford from virtual node
        int[] h = new int[n + 1];
        Arrays.fill(h, Integer.MAX_VALUE); h[n] = 0;
        for (int i = 0; i < n; i++)
            for (int[] e : augEdges)
                if (h[e[0]] != Integer.MAX_VALUE && h[e[0]] + e[2] < h[e[1]])
                    h[e[1]] = h[e[0]] + e[2];

        // Reweight edges
        List<int[]>[] graph = new List[n];
        for (int i = 0; i < n; i++) graph[i] = new ArrayList<>();
        for (int[] e : edges)
            graph[e[0]].add(new int[]{e[1], e[2] + h[e[0]] - h[e[1]]});

        // Dijkstra from each node
        int[][] result = new int[n][n];
        for (int s = 0; s < n; s++) {
            int[] dist = dijkstra(graph, s, n);
            for (int t = 0; t < n; t++)
                result[s][t] = dist[t] == Integer.MAX_VALUE ? Integer.MAX_VALUE : dist[t] - h[s] + h[t];
        }
        return result;
    }

    private int[] dijkstra(List<int[]>[] graph, int src, int n) {
        int[] dist = new int[n]; Arrays.fill(dist, Integer.MAX_VALUE); dist[src] = 0;
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[1] - b[1]);
        pq.offer(new int[]{src, 0});
        while (!pq.isEmpty()) {
            int[] cur = pq.poll();
            if (cur[1] > dist[cur[0]]) continue;
            for (int[] nei : graph[cur[0]]) {
                if (dist[cur[0]] + nei[1] < dist[nei[0]]) { dist[nei[0]] = dist[cur[0]] + nei[1]; pq.offer(new int[]{nei[0], dist[nei[0]]}); }
            }
        }
        return dist;
    }

    public static void main(String[] args) {
        Problem37_JohnsonsAlgorithm solver = new Problem37_JohnsonsAlgorithm();
        int[][] res = solver.johnson(4, new int[][]{{0,1,1},{1,2,2},{2,3,3},{0,3,10}});
        for (int[] row : res) System.out.println(Arrays.toString(row));
    }
}
