import java.util.*;

/**
 * Problem: Number of Ways to Arrive at Destination
 * Count shortest paths from 0 to n-1.
 *
 * Approach: Dijkstra tracking count of shortest paths
 *
 * Time Complexity: O((V + E) log V)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Counting equally optimal routing paths for load balancing.
 */
public class Problem20_NumberOfWaysToArriveAtDestination {

    public int countPaths(int n, int[][] roads) {
        long MOD = 1_000_000_007;
        List<long[]>[] graph = new List[n];
        for (int i = 0; i < n; i++) graph[i] = new ArrayList<>();
        for (int[] r : roads) { graph[r[0]].add(new long[]{r[1], r[2]}); graph[r[1]].add(new long[]{r[0], r[2]}); }

        long[] dist = new long[n]; Arrays.fill(dist, Long.MAX_VALUE); dist[0] = 0;
        long[] ways = new long[n]; ways[0] = 1;
        PriorityQueue<long[]> pq = new PriorityQueue<>((a, b) -> Long.compare(a[1], b[1]));
        pq.offer(new long[]{0, 0});

        while (!pq.isEmpty()) {
            long[] cur = pq.poll();
            int u = (int) cur[0];
            if (cur[1] > dist[u]) continue;
            for (long[] nei : graph[u]) {
                int v = (int) nei[0]; long w = nei[1];
                if (dist[u] + w < dist[v]) { dist[v] = dist[u] + w; ways[v] = ways[u]; pq.offer(new long[]{v, dist[v]}); }
                else if (dist[u] + w == dist[v]) ways[v] = (ways[v] + ways[u]) % MOD;
            }
        }
        return (int) ways[n - 1];
    }

    public static void main(String[] args) {
        Problem20_NumberOfWaysToArriveAtDestination solver = new Problem20_NumberOfWaysToArriveAtDestination();
        System.out.println(solver.countPaths(7, new int[][]{{0,6,7},{0,1,2},{1,2,3},{1,3,3},{6,3,3},{3,5,1},{6,5,1},{2,5,1},{0,4,5},{4,6,2}})); // 4
    }
}
