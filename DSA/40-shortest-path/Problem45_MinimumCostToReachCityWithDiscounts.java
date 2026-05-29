import java.util.*;

/**
 * Problem: Minimum Cost to Reach City With Discounts
 * Find cheapest path where you can halve toll on up to k edges.
 *
 * Approach: Dijkstra with state (node, discountsUsed)
 *
 * Time Complexity: O((V*K + E*K) * log(V*K))
 * Space Complexity: O(V * K)
 *
 * Production Analogy: Finding cheapest cloud routing with limited free-tier credits.
 */
public class Problem45_MinimumCostToReachCityWithDiscounts {

    public int minimumCost(int n, int[][] highways, int discounts) {
        List<int[]>[] graph = new List[n];
        for (int i = 0; i < n; i++) graph[i] = new ArrayList<>();
        for (int[] h : highways) { graph[h[0]].add(new int[]{h[1], h[2]}); graph[h[1]].add(new int[]{h[0], h[2]}); }

        int[][] dist = new int[n][discounts + 1];
        for (int[] row : dist) Arrays.fill(row, Integer.MAX_VALUE);
        dist[0][0] = 0;

        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[2] - b[2]);
        pq.offer(new int[]{0, 0, 0}); // node, discounts used, cost

        while (!pq.isEmpty()) {
            int[] cur = pq.poll();
            int u = cur[0], d = cur[1], cost = cur[2];
            if (u == n - 1) return cost;
            if (cost > dist[u][d]) continue;
            for (int[] nei : graph[u]) {
                // Without discount
                if (cost + nei[1] < dist[nei[0]][d]) {
                    dist[nei[0]][d] = cost + nei[1];
                    pq.offer(new int[]{nei[0], d, dist[nei[0]][d]});
                }
                // With discount
                if (d < discounts && cost + nei[1]/2 < dist[nei[0]][d+1]) {
                    dist[nei[0]][d+1] = cost + nei[1]/2;
                    pq.offer(new int[]{nei[0], d+1, dist[nei[0]][d+1]});
                }
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        Problem45_MinimumCostToReachCityWithDiscounts solver = new Problem45_MinimumCostToReachCityWithDiscounts();
        System.out.println(solver.minimumCost(4, new int[][]{{0,1,4},{1,2,3},{2,3,1},{0,3,10}}, 1)); // 5
    }
}
