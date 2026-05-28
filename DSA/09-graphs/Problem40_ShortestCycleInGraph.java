import java.util.*;

/**
 * Problem 40: Shortest Cycle in a Graph (LeetCode 2608)
 * 
 * Approach: BFS from each node. If we find an already-visited node (not parent), cycle found.
 * Time: O(V * (V + E)), Space: O(V + E)
 * 
 * Production Analogy: Finding the tightest feedback loop in an event-driven architecture.
 */
public class Problem40_ShortestCycleInGraph {
    
    public int findShortestCycle(int n, int[][] edges) {
        List<Integer>[] adj = new List[n];
        for (int i = 0; i < n; i++) adj[i] = new ArrayList<>();
        for (int[] e : edges) { adj[e[0]].add(e[1]); adj[e[1]].add(e[0]); }
        int ans = Integer.MAX_VALUE;
        for (int i = 0; i < n; i++) {
            int[] dist = new int[n];
            Arrays.fill(dist, -1);
            dist[i] = 0;
            Queue<Integer> q = new LinkedList<>();
            q.offer(i);
            while (!q.isEmpty()) {
                int node = q.poll();
                for (int nei : adj[node]) {
                    if (dist[nei] == -1) { dist[nei] = dist[node] + 1; q.offer(nei); }
                    else if (dist[nei] >= dist[node]) ans = Math.min(ans, dist[nei] + dist[node] + 1);
                }
            }
        }
        return ans == Integer.MAX_VALUE ? -1 : ans;
    }
    
    public static void main(String[] args) {
        Problem40_ShortestCycleInGraph sol = new Problem40_ShortestCycleInGraph();
        System.out.println(sol.findShortestCycle(7, new int[][]{{0,1},{1,2},{2,0},{3,4},{4,5},{5,6},{6,3}})); // 3
        System.out.println(sol.findShortestCycle(4, new int[][]{{0,1},{0,2}})); // -1
    }
}
