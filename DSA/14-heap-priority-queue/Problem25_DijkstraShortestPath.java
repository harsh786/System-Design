import java.util.*;

/**
 * Problem 25: Dijkstra's Shortest Path Algorithm
 * 
 * Approach: Min-heap priority queue processing vertices by shortest known distance.
 * Relax edges greedily.
 * 
 * Time Complexity: O((V + E) log V)
 * Space Complexity: O(V + E)
 * 
 * Production Analogy: Network routing protocols (OSPF), CDN path optimization,
 * finding lowest-latency path between data centers.
 */
public class Problem25_DijkstraShortestPath {
    
    public int[] dijkstra(int n, List<List<int[]>> graph, int src) {
        int[] dist = new int[n];
        Arrays.fill(dist, Integer.MAX_VALUE);
        dist[src] = 0;
        
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[1] - b[1]);
        pq.offer(new int[]{src, 0});
        
        while (!pq.isEmpty()) {
            int[] curr = pq.poll();
            int u = curr[0], d = curr[1];
            if (d > dist[u]) continue;
            for (int[] edge : graph.get(u)) {
                int v = edge[0], w = edge[1];
                if (dist[u] + w < dist[v]) {
                    dist[v] = dist[u] + w;
                    pq.offer(new int[]{v, dist[v]});
                }
            }
        }
        return dist;
    }
    
    public static void main(String[] args) {
        Problem25_DijkstraShortestPath sol = new Problem25_DijkstraShortestPath();
        int n = 5;
        List<List<int[]>> graph = new ArrayList<>();
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        graph.get(0).add(new int[]{1, 4});
        graph.get(0).add(new int[]{2, 1});
        graph.get(2).add(new int[]{1, 2});
        graph.get(1).add(new int[]{3, 1});
        graph.get(2).add(new int[]{3, 5});
        graph.get(3).add(new int[]{4, 3});
        
        System.out.println(Arrays.toString(sol.dijkstra(n, graph, 0))); // [0, 3, 1, 4, 7]
    }
}
