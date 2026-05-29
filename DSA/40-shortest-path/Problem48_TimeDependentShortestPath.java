import java.util.*;

/**
 * Problem: Time-Dependent Shortest Path
 * Edge weights change based on departure time.
 *
 * Approach: Modified Dijkstra where edge weight is a function of current time
 *
 * Time Complexity: O((V + E) log V)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Rush-hour aware navigation / time-varying network congestion routing.
 */
public class Problem48_TimeDependentShortestPath {

    @FunctionalInterface
    interface TravelTime { int compute(int departureTime); }

    public int shortestPath(int n, int[][][] edges, int src, int dst) {
        // edges[u] = list of {v, baseWeight, congestionFactor}
        List<int[]>[] graph = new List[n];
        for (int i = 0; i < n; i++) graph[i] = new ArrayList<>();
        for (int u = 0; u < n; u++)
            for (int[] e : edges[u]) graph[u].add(e);

        int[] dist = new int[n];
        Arrays.fill(dist, Integer.MAX_VALUE);
        dist[src] = 0;
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[1] - b[1]);
        pq.offer(new int[]{src, 0});

        while (!pq.isEmpty()) {
            int[] cur = pq.poll();
            int u = cur[0], time = cur[1];
            if (u == dst) return time;
            if (time > dist[u]) continue;
            for (int[] nei : graph[u]) {
                int v = nei[0], weight = nei[1] + (time / 10) * nei[2]; // time-dependent weight
                int arrival = time + weight;
                if (arrival < dist[v]) { dist[v] = arrival; pq.offer(new int[]{v, arrival}); }
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        Problem48_TimeDependentShortestPath solver = new Problem48_TimeDependentShortestPath();
        int[][][] edges = {
            {{1, 5, 1}, {2, 10, 0}},  // from 0
            {{2, 3, 0}, {3, 7, 2}},   // from 1
            {{3, 2, 0}},              // from 2
            {}                         // from 3
        };
        System.out.println(solver.shortestPath(4, edges, 0, 3)); // depends on time function
    }
}
