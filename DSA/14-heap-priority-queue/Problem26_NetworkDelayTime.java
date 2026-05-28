import java.util.*;

/**
 * Problem 26: Network Delay Time (LeetCode 743)
 * 
 * Approach: Dijkstra from source node. Answer is max distance to any reachable node.
 * 
 * Time Complexity: O((V + E) log V)
 * Space Complexity: O(V + E)
 * 
 * Production Analogy: Calculating worst-case propagation delay in a distributed
 * system for determining timeout values.
 */
public class Problem26_NetworkDelayTime {
    
    public int networkDelayTime(int[][] times, int n, int k) {
        List<List<int[]>> graph = new ArrayList<>();
        for (int i = 0; i <= n; i++) graph.add(new ArrayList<>());
        for (int[] t : times) graph.get(t[0]).add(new int[]{t[1], t[2]});
        
        int[] dist = new int[n + 1];
        Arrays.fill(dist, Integer.MAX_VALUE);
        dist[k] = 0;
        
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[1] - b[1]);
        pq.offer(new int[]{k, 0});
        
        while (!pq.isEmpty()) {
            int[] curr = pq.poll();
            if (curr[1] > dist[curr[0]]) continue;
            for (int[] edge : graph.get(curr[0])) {
                int newDist = dist[curr[0]] + edge[1];
                if (newDist < dist[edge[0]]) {
                    dist[edge[0]] = newDist;
                    pq.offer(new int[]{edge[0], newDist});
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
        Problem26_NetworkDelayTime sol = new Problem26_NetworkDelayTime();
        System.out.println(sol.networkDelayTime(new int[][]{{2,1,1},{2,3,1},{3,4,1}}, 4, 2)); // 2
        System.out.println(sol.networkDelayTime(new int[][]{{1,2,1}}, 2, 2)); // -1
    }
}
