import java.util.*;

/**
 * Problem: Shortest Cycle in Graph (LeetCode 2608)
 * Approach: BFS from each node, track distances; cycle found when visiting already-visited node
 * Time: O(V*(V+E)), Space: O(V)
 * Production Analogy: Finding minimum circular dependency length in service mesh
 */
public class Problem50_ShortestCycleInGraph {
    public int findShortestCycle(int n, int[][] edges) {
        List<List<Integer>> graph = new ArrayList<>();
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] e : edges) { graph.get(e[0]).add(e[1]); graph.get(e[1]).add(e[0]); }
        int min = Integer.MAX_VALUE;
        for (int i = 0; i < n; i++) {
            int[] dist = new int[n];
            Arrays.fill(dist, -1);
            dist[i] = 0;
            Queue<int[]> q = new LinkedList<>(); // [node, parent]
            q.offer(new int[]{i, -1});
            while (!q.isEmpty()) {
                int[] curr = q.poll();
                for (int next : graph.get(curr[0])) {
                    if (dist[next] == -1) {
                        dist[next] = dist[curr[0]] + 1;
                        q.offer(new int[]{next, curr[0]});
                    } else if (next != curr[1]) {
                        min = Math.min(min, dist[curr[0]] + dist[next] + 1);
                    }
                }
            }
        }
        return min == Integer.MAX_VALUE ? -1 : min;
    }

    public static void main(String[] args) {
        int[][] edges = {{0,1},{1,2},{2,0},{3,4},{4,5},{5,3}};
        System.out.println(new Problem50_ShortestCycleInGraph().findShortestCycle(6, edges)); // 3
    }
}
