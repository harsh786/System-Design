import java.util.*;

/**
 * Problem 11: Network Delay Time (LeetCode 743) - Dijkstra's Algorithm
 * 
 * Approach: Dijkstra's shortest path from source to all nodes. Return max distance.
 * Time: O(E log V), Space: O(V + E)
 * 
 * Production Analogy: Calculating worst-case latency for a request propagating through a service mesh.
 */
public class Problem11_NetworkDelayTime {
    
    public int networkDelayTime(int[][] times, int n, int k) {
        List<int[]>[] adj = new List[n + 1];
        for (int i = 0; i <= n; i++) adj[i] = new ArrayList<>();
        for (int[] t : times) adj[t[0]].add(new int[]{t[1], t[2]});
        
        int[] dist = new int[n + 1];
        Arrays.fill(dist, Integer.MAX_VALUE);
        dist[k] = 0;
        PriorityQueue<int[]> pq = new PriorityQueue<>((a,b) -> a[1] - b[1]);
        pq.offer(new int[]{k, 0});
        while (!pq.isEmpty()) {
            int[] curr = pq.poll();
            if (curr[1] > dist[curr[0]]) continue;
            for (int[] next : adj[curr[0]]) {
                int nd = curr[1] + next[1];
                if (nd < dist[next[0]]) { dist[next[0]] = nd; pq.offer(new int[]{next[0], nd}); }
            }
        }
        int max = 0;
        for (int i = 1; i <= n; i++) { if (dist[i] == Integer.MAX_VALUE) return -1; max = Math.max(max, dist[i]); }
        return max;
    }
    
    public static void main(String[] args) {
        Problem11_NetworkDelayTime sol = new Problem11_NetworkDelayTime();
        System.out.println(sol.networkDelayTime(new int[][]{{2,1,1},{2,3,1},{3,4,1}}, 4, 2)); // 2
        System.out.println(sol.networkDelayTime(new int[][]{{1,2,1}}, 2, 2)); // -1
        System.out.println(sol.networkDelayTime(new int[][]{{1,2,1}}, 2, 1)); // 1
    }
}
