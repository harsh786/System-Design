import java.util.*;

/**
 * Problem: Shortest Path with Alternating Colors
 * Find shortest path using alternating red/blue edges.
 *
 * Approach: BFS with state (node, lastColor)
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Routing through alternating network layers (e.g., public/private hops).
 */
public class Problem44_ShortestPathWithAlternatingColors {

    public int[] shortestAlternatingPaths(int n, int[][] redEdges, int[][] blueEdges) {
        List<Integer>[][] graph = new List[2][n];
        for (int c = 0; c < 2; c++) for (int i = 0; i < n; i++) graph[c][i] = new ArrayList<>();
        for (int[] e : redEdges) graph[0][e[0]].add(e[1]);
        for (int[] e : blueEdges) graph[1][e[0]].add(e[1]);

        int[][] dist = new int[2][n];
        for (int[] row : dist) Arrays.fill(row, Integer.MAX_VALUE);
        dist[0][0] = dist[1][0] = 0;

        Queue<int[]> q = new LinkedList<>();
        q.offer(new int[]{0, 0}); q.offer(new int[]{0, 1}); // {node, lastColor}

        while (!q.isEmpty()) {
            int[] cur = q.poll();
            int node = cur[0], color = cur[1];
            int nextColor = 1 - color;
            for (int nei : graph[nextColor][node]) {
                if (dist[nextColor][nei] > dist[color][node] + 1) {
                    dist[nextColor][nei] = dist[color][node] + 1;
                    q.offer(new int[]{nei, nextColor});
                }
            }
        }

        int[] ans = new int[n];
        for (int i = 0; i < n; i++) {
            ans[i] = Math.min(dist[0][i], dist[1][i]);
            if (ans[i] == Integer.MAX_VALUE) ans[i] = -1;
        }
        return ans;
    }

    public static void main(String[] args) {
        Problem44_ShortestPathWithAlternatingColors solver = new Problem44_ShortestPathWithAlternatingColors();
        System.out.println(Arrays.toString(solver.shortestAlternatingPaths(3, new int[][]{{0,1},{1,2}}, new int[][]{})); 
    }
}
