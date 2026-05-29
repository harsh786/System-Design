import java.util.*;

/**
 * Problem: Network Delay Time (Dijkstra)
 * Find time for signal to reach all nodes from source.
 *
 * Approach: Dijkstra's algorithm with min-heap
 *
 * Time Complexity: O((V + E) log V)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Calculating maximum network latency from a server to all clients.
 */
public class Problem01_NetworkDelayTime {

    public int networkDelayTime(int[][] times, int n, int k) {
        List<int[]>[] graph = new List[n + 1];
        for (int i = 0; i <= n; i++) graph[i] = new ArrayList<>();
        for (int[] t : times) graph[t[0]].add(new int[]{t[1], t[2]});

        int[] dist = new int[n + 1];
        Arrays.fill(dist, Integer.MAX_VALUE);
        dist[k] = 0;

        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[1] - b[1]);
        pq.offer(new int[]{k, 0});

        while (!pq.isEmpty()) {
            int[] cur = pq.poll();
            if (cur[1] > dist[cur[0]]) continue;
            for (int[] nei : graph[cur[0]]) {
                int newDist = dist[cur[0]] + nei[1];
                if (newDist < dist[nei[0]]) {
                    dist[nei[0]] = newDist;
                    pq.offer(new int[]{nei[0], newDist});
                }
            }
        }

        int max = 0;
        for (int i = 1; i <= n; i++) {
            if (dist[i] == Integer.MAX_VALUE) return -1;
            max = Math.max(max, dist[i]);
        }
        return max;
    }

    public static void main(String[] args) {
        Problem01_NetworkDelayTime solver = new Problem01_NetworkDelayTime();
        System.out.println(solver.networkDelayTime(new int[][]{{2,1,1},{2,3,1},{3,4,1}}, 4, 2)); // 2
    }
}
