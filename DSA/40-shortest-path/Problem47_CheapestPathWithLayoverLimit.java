import java.util.*;

/**
 * Problem: Cheapest Path with Layover Limit
 * Like flights with k stops but generalized to any weighted graph.
 *
 * Approach: Modified Dijkstra with state (node, stops_remaining)
 *
 * Time Complexity: O(K * E * log(K*V))
 * Space Complexity: O(K * V)
 *
 * Production Analogy: Finding cheapest routing path with maximum hop count (TTL).
 */
public class Problem47_CheapestPathWithLayoverLimit {

    public int cheapestPath(int n, int[][] edges, int src, int dst, int maxStops) {
        List<int[]>[] graph = new List[n];
        for (int i = 0; i < n; i++) graph[i] = new ArrayList<>();
        for (int[] e : edges) graph[e[0]].add(new int[]{e[1], e[2]});

        int[][] dist = new int[n][maxStops + 2];
        for (int[] row : dist) Arrays.fill(row, Integer.MAX_VALUE);
        dist[src][0] = 0;

        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[2] - b[2]);
        pq.offer(new int[]{src, 0, 0}); // node, stops, cost

        while (!pq.isEmpty()) {
            int[] cur = pq.poll();
            int u = cur[0], stops = cur[1], cost = cur[2];
            if (u == dst) return cost;
            if (stops > maxStops) continue;
            if (cost > dist[u][stops]) continue;
            for (int[] nei : graph[u]) {
                int nc = cost + nei[1];
                if (nc < dist[nei[0]][stops + 1]) {
                    dist[nei[0]][stops + 1] = nc;
                    pq.offer(new int[]{nei[0], stops + 1, nc});
                }
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        Problem47_CheapestPathWithLayoverLimit solver = new Problem47_CheapestPathWithLayoverLimit();
        System.out.println(solver.cheapestPath(4, new int[][]{{0,1,1},{0,2,5},{1,2,1},{2,3,1}}, 0, 3, 1)); // 6
    }
}
