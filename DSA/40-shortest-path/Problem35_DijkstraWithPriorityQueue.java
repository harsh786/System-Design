import java.util.*;

/**
 * Problem: Dijkstra with Priority Queue (canonical implementation)
 *
 * Approach: Lazy deletion Dijkstra with min-heap
 *
 * Time Complexity: O((V + E) log V)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: GPS navigation finding shortest route in road networks.
 */
public class Problem35_DijkstraWithPriorityQueue {

    public int[] dijkstra(int n, int[][] edges, int src) {
        List<int[]>[] graph = new List[n];
        for (int i = 0; i < n; i++) graph[i] = new ArrayList<>();
        for (int[] e : edges) { graph[e[0]].add(new int[]{e[1], e[2]}); graph[e[1]].add(new int[]{e[0], e[2]}); }

        int[] dist = new int[n];
        Arrays.fill(dist, Integer.MAX_VALUE);
        dist[src] = 0;
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[1] - b[1]);
        pq.offer(new int[]{src, 0});

        while (!pq.isEmpty()) {
            int[] cur = pq.poll();
            if (cur[1] > dist[cur[0]]) continue; // lazy deletion
            for (int[] nei : graph[cur[0]]) {
                int newDist = dist[cur[0]] + nei[1];
                if (newDist < dist[nei[0]]) {
                    dist[nei[0]] = newDist;
                    pq.offer(new int[]{nei[0], newDist});
                }
            }
        }
        return dist;
    }

    public static void main(String[] args) {
        Problem35_DijkstraWithPriorityQueue solver = new Problem35_DijkstraWithPriorityQueue();
        System.out.println(Arrays.toString(solver.dijkstra(5, new int[][]{{0,1,4},{0,2,1},{2,1,2},{1,3,1},{2,3,5},{3,4,3}}, 0)));
    }
}
