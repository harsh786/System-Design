import java.util.*;

/**
 * Problem 29: Cheapest Flights Within K Stops (LeetCode 787)
 * 
 * Approach: Modified Dijkstra with stops constraint. Min-heap by (cost, node, stops).
 * 
 * Time Complexity: O(E * K * log(E*K))
 * Space Complexity: O(V * K)
 * 
 * Production Analogy: Finding cheapest message routing path with hop limit in a
 * multi-region service mesh.
 */
public class Problem29_CheapestFlightsWithinKStops {
    
    public int findCheapestPrice(int n, int[][] flights, int src, int dst, int k) {
        List<List<int[]>> graph = new ArrayList<>();
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] f : flights) graph.get(f[0]).add(new int[]{f[1], f[2]});
        
        int[] stops = new int[n];
        Arrays.fill(stops, Integer.MAX_VALUE);
        
        // [cost, node, stopsUsed]
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[0] - b[0]);
        pq.offer(new int[]{0, src, 0});
        
        while (!pq.isEmpty()) {
            int[] curr = pq.poll();
            int cost = curr[0], node = curr[1], s = curr[2];
            if (node == dst) return cost;
            if (s > k || s >= stops[node]) continue;
            stops[node] = s;
            for (int[] next : graph.get(node)) {
                pq.offer(new int[]{cost + next[1], next[0], s + 1});
            }
        }
        return -1;
    }
    
    public static void main(String[] args) {
        Problem29_CheapestFlightsWithinKStops sol = new Problem29_CheapestFlightsWithinKStops();
        System.out.println(sol.findCheapestPrice(4, new int[][]{{0,1,100},{1,2,100},{2,0,100},{1,3,600},{2,3,200}}, 0, 3, 1)); // 700
        System.out.println(sol.findCheapestPrice(3, new int[][]{{0,1,100},{1,2,100},{0,2,500}}, 0, 2, 1)); // 200
    }
}
