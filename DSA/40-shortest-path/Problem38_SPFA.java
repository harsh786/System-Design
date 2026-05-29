import java.util.*;

/**
 * Problem: SPFA (Shortest Path Faster Algorithm)
 * Optimized Bellman-Ford using queue.
 *
 * Approach: Queue-based relaxation, only enqueue nodes whose distance changed
 *
 * Time Complexity: O(V*E) worst, O(E) average
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Incremental routing table updates in network protocols (like BGP).
 */
public class Problem38_SPFA {

    public int[] spfa(int n, int[][] edges, int src) {
        List<int[]>[] graph = new List[n];
        for (int i = 0; i < n; i++) graph[i] = new ArrayList<>();
        for (int[] e : edges) graph[e[0]].add(new int[]{e[1], e[2]});

        int[] dist = new int[n];
        Arrays.fill(dist, Integer.MAX_VALUE);
        dist[src] = 0;
        boolean[] inQueue = new boolean[n];
        int[] count = new int[n];
        Queue<Integer> q = new LinkedList<>();
        q.offer(src); inQueue[src] = true;

        while (!q.isEmpty()) {
            int u = q.poll(); inQueue[u] = false;
            for (int[] nei : graph[u]) {
                if (dist[u] + nei[1] < dist[nei[0]]) {
                    dist[nei[0]] = dist[u] + nei[1];
                    if (!inQueue[nei[0]]) {
                        q.offer(nei[0]); inQueue[nei[0]] = true;
                        if (++count[nei[0]] >= n) throw new RuntimeException("Negative cycle");
                    }
                }
            }
        }
        return dist;
    }

    public static void main(String[] args) {
        Problem38_SPFA solver = new Problem38_SPFA();
        System.out.println(Arrays.toString(solver.spfa(4, new int[][]{{0,1,1},{1,2,-1},{2,3,2},{0,3,5}}, 0)));
    }
}
