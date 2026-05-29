import java.util.*;

/**
 * Problem: 0-1 BFS
 * Shortest path in graph with edge weights 0 or 1.
 *
 * Approach: Deque-based BFS - push 0-weight to front, 1-weight to back
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Finding cheapest path where some links are free (internal) vs paid.
 */
public class Problem12_ZeroOneBFS {

    public int[] shortestPath(int n, int[][] edges, int src) {
        List<int[]>[] graph = new List[n];
        for (int i = 0; i < n; i++) graph[i] = new ArrayList<>();
        for (int[] e : edges) { graph[e[0]].add(new int[]{e[1], e[2]}); graph[e[1]].add(new int[]{e[0], e[2]}); }

        int[] dist = new int[n];
        Arrays.fill(dist, Integer.MAX_VALUE);
        dist[src] = 0;
        Deque<Integer> dq = new ArrayDeque<>();
        dq.offer(src);

        while (!dq.isEmpty()) {
            int u = dq.poll();
            for (int[] nei : graph[u]) {
                int v = nei[0], w = nei[1];
                if (dist[u] + w < dist[v]) {
                    dist[v] = dist[u] + w;
                    if (w == 0) dq.offerFirst(v); else dq.offerLast(v);
                }
            }
        }
        return dist;
    }

    public static void main(String[] args) {
        Problem12_ZeroOneBFS solver = new Problem12_ZeroOneBFS();
        System.out.println(Arrays.toString(solver.shortestPath(4, new int[][]{{0,1,0},{1,2,1},{0,3,1},{3,2,0}}, 0)));
    }
}
