import java.util.*;

/**
 * Problem 12: Cheapest Flights Within K Stops (LeetCode 787)
 * 
 * Approach: Bellman-Ford with K+1 relaxation rounds, or BFS with pruning.
 * Time: O(K * E), Space: O(V)
 * 
 * Production Analogy: Finding cheapest CDN path with max hop count constraint.
 */
public class Problem12_CheapestFlightsWithinKStops {
    
    public int findCheapestPrice(int n, int[][] flights, int src, int dst, int k) {
        int[] dist = new int[n];
        Arrays.fill(dist, Integer.MAX_VALUE);
        dist[src] = 0;
        for (int i = 0; i <= k; i++) {
            int[] temp = dist.clone();
            for (int[] f : flights) {
                if (dist[f[0]] != Integer.MAX_VALUE)
                    temp[f[1]] = Math.min(temp[f[1]], dist[f[0]] + f[2]);
            }
            dist = temp;
        }
        return dist[dst] == Integer.MAX_VALUE ? -1 : dist[dst];
    }
    
    public static void main(String[] args) {
        Problem12_CheapestFlightsWithinKStops sol = new Problem12_CheapestFlightsWithinKStops();
        System.out.println(sol.findCheapestPrice(4, new int[][]{{0,1,100},{1,2,100},{2,0,100},{1,3,600},{2,3,200}}, 0, 3, 1)); // 700
        System.out.println(sol.findCheapestPrice(3, new int[][]{{0,1,100},{1,2,100},{0,2,500}}, 0, 2, 1)); // 200
        System.out.println(sol.findCheapestPrice(3, new int[][]{{0,1,100},{1,2,100},{0,2,500}}, 0, 2, 0)); // 500
    }
}
