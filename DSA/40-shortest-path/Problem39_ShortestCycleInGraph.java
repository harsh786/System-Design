import java.util.*;

/**
 * Problem: Shortest Cycle in Graph
 *
 * Approach: BFS from each node, find shortest cycle through that node
 *
 * Time Complexity: O(V * (V + E))
 * Space Complexity: O(V)
 *
 * Production Analogy: Finding shortest circular dependency in a system.
 */
public class Problem39_ShortestCycleInGraph {

    public int findShortestCycle(int n, int[][] edges) {
        List<List<Integer>> graph = new ArrayList<>();
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] e : edges) { graph.get(e[0]).add(e[1]); graph.get(e[1]).add(e[0]); }

        int ans = Integer.MAX_VALUE;
        for (int i = 0; i < n; i++) {
            int[] dist = new int[n]; Arrays.fill(dist, -1); dist[i] = 0;
            Queue<Integer> q = new LinkedList<>(); q.offer(i);
            int[] parent = new int[n]; Arrays.fill(parent, -1);
            while (!q.isEmpty()) {
                int u = q.poll();
                for (int v : graph.get(u)) {
                    if (dist[v] == -1) { dist[v] = dist[u] + 1; parent[v] = u; q.offer(v); }
                    else if (parent[u] != v && parent[v] != u)
                        ans = Math.min(ans, dist[u] + dist[v] + 1);
                }
            }
        }
        return ans == Integer.MAX_VALUE ? -1 : ans;
    }

    public static void main(String[] args) {
        Problem39_ShortestCycleInGraph solver = new Problem39_ShortestCycleInGraph();
        System.out.println(solver.findShortestCycle(4, new int[][]{{0,1},{1,2},{2,3},{3,0},{0,2}})); // 3
    }
}
