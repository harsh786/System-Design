import java.util.*;

/**
 * Problem: Minimum Weighted Subgraph With Required Paths
 * Find min weight subgraph where src1->dest and src2->dest paths exist.
 *
 * Approach: Dijkstra from src1, src2, and reverse graph from dest. For each node v,
 * answer = min(dist1[v] + dist2[v] + distDest[v])
 *
 * Time Complexity: O((V + E) log V)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Minimizing infrastructure cost while ensuring two sources reach a sink.
 */
public class Problem19_MinimumWeightedSubgraphWithRequiredPaths {

    public long minimumWeight(int n, int[][] edges, int src1, int src2, int dest) {
        List<long[]>[] graph = new List[n], rGraph = new List[n];
        for (int i = 0; i < n; i++) { graph[i] = new ArrayList<>(); rGraph[i] = new ArrayList<>(); }
        for (int[] e : edges) { graph[e[0]].add(new long[]{e[1], e[2]}); rGraph[e[1]].add(new long[]{e[0], e[2]}); }

        long[] d1 = dijkstra(graph, src1, n);
        long[] d2 = dijkstra(graph, src2, n);
        long[] dd = dijkstra(rGraph, dest, n);

        long ans = Long.MAX_VALUE;
        for (int i = 0; i < n; i++)
            if (d1[i] != Long.MAX_VALUE && d2[i] != Long.MAX_VALUE && dd[i] != Long.MAX_VALUE)
                ans = Math.min(ans, d1[i] + d2[i] + dd[i]);
        return ans == Long.MAX_VALUE ? -1 : ans;
    }

    private long[] dijkstra(List<long[]>[] graph, int src, int n) {
        long[] dist = new long[n]; Arrays.fill(dist, Long.MAX_VALUE); dist[src] = 0;
        PriorityQueue<long[]> pq = new PriorityQueue<>((a, b) -> Long.compare(a[1], b[1]));
        pq.offer(new long[]{src, 0});
        while (!pq.isEmpty()) {
            long[] cur = pq.poll();
            int u = (int) cur[0];
            if (cur[1] > dist[u]) continue;
            for (long[] nei : graph[u]) {
                int v = (int) nei[0];
                if (dist[u] + nei[1] < dist[v]) { dist[v] = dist[u] + nei[1]; pq.offer(new long[]{v, dist[v]}); }
            }
        }
        return dist;
    }

    public static void main(String[] args) {
        Problem19_MinimumWeightedSubgraphWithRequiredPaths solver = new Problem19_MinimumWeightedSubgraphWithRequiredPaths();
        System.out.println(solver.minimumWeight(6, new int[][]{{0,2,2},{0,5,6},{1,0,3},{1,4,5},{2,1,1},{2,3,3},{2,3,4},{3,4,2},{4,5,1}}, 0, 1, 5));
    }
}
