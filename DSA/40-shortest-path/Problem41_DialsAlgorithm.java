import java.util.*;

/**
 * Problem: Dial's Algorithm
 * Shortest path when edge weights are small integers [0, W].
 *
 * Approach: Bucket-based (array of queues indexed by distance)
 *
 * Time Complexity: O(V + E + W*V)
 * Space Complexity: O(W*V)
 *
 * Production Analogy: Priority routing with discrete latency buckets.
 */
public class Problem41_DialsAlgorithm {

    public int[] dial(int n, int[][] edges, int src, int maxWeight) {
        List<int[]>[] graph = new List[n];
        for (int i = 0; i < n; i++) graph[i] = new ArrayList<>();
        for (int[] e : edges) { graph[e[0]].add(new int[]{e[1], e[2]}); graph[e[1]].add(new int[]{e[0], e[2]}); }

        int[] dist = new int[n];
        Arrays.fill(dist, Integer.MAX_VALUE);
        dist[src] = 0;

        int maxDist = maxWeight * n;
        List<Integer>[] buckets = new List[maxDist + 1];
        for (int i = 0; i <= maxDist; i++) buckets[i] = new ArrayList<>();
        buckets[0].add(src);

        int idx = 0;
        for (int processed = 0; processed < n; ) {
            while (idx <= maxDist && buckets[idx].isEmpty()) idx++;
            if (idx > maxDist) break;
            List<Integer> bucket = buckets[idx];
            buckets[idx] = new ArrayList<>();
            for (int u : bucket) {
                if (dist[u] != idx) continue;
                processed++;
                for (int[] nei : graph[u]) {
                    int newDist = dist[u] + nei[1];
                    if (newDist < dist[nei[0]]) {
                        dist[nei[0]] = newDist;
                        buckets[newDist].add(nei[0]);
                    }
                }
            }
        }
        return dist;
    }

    public static void main(String[] args) {
        Problem41_DialsAlgorithm solver = new Problem41_DialsAlgorithm();
        System.out.println(Arrays.toString(solver.dial(4, new int[][]{{0,1,2},{0,2,4},{1,2,1},{2,3,3}}, 0, 4)));
    }
}
