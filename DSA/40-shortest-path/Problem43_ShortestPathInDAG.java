import java.util.*;

/**
 * Problem: Shortest Path in DAG
 * Use topological sort for O(V+E) shortest path in DAG.
 *
 * Approach: Topological sort, then relax in order
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Computing minimum cost through a pipeline DAG.
 */
public class Problem43_ShortestPathInDAG {

    public int[] shortestPath(int n, int[][] edges, int src) {
        List<int[]>[] graph = new List[n];
        int[] inDeg = new int[n];
        for (int i = 0; i < n; i++) graph[i] = new ArrayList<>();
        for (int[] e : edges) { graph[e[0]].add(new int[]{e[1], e[2]}); inDeg[e[1]]++; }

        Queue<Integer> q = new LinkedList<>();
        for (int i = 0; i < n; i++) if (inDeg[i] == 0) q.offer(i);
        List<Integer> order = new ArrayList<>();
        while (!q.isEmpty()) { int u = q.poll(); order.add(u); for (int[] nei : graph[u]) if (--inDeg[nei[0]]==0) q.offer(nei[0]); }

        int[] dist = new int[n];
        Arrays.fill(dist, Integer.MAX_VALUE);
        dist[src] = 0;
        for (int u : order) {
            if (dist[u] == Integer.MAX_VALUE) continue;
            for (int[] nei : graph[u])
                dist[nei[0]] = Math.min(dist[nei[0]], dist[u] + nei[1]);
        }
        return dist;
    }

    public static void main(String[] args) {
        Problem43_ShortestPathInDAG solver = new Problem43_ShortestPathInDAG();
        System.out.println(Arrays.toString(solver.shortestPath(5, new int[][]{{0,1,2},{0,2,4},{1,2,1},{1,3,7},{2,4,3}}, 0)));
    }
}
