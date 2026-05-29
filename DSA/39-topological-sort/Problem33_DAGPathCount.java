import java.util.*;

/**
 * Problem: DAG Path Count
 * Count number of paths from source to destination in a DAG.
 *
 * Approach: Topological sort + DP: paths[v] = sum of paths[u] for all u->v
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Counting possible execution traces through a workflow.
 */
public class Problem33_DAGPathCount {

    public int countPaths(int n, int[][] edges, int src, int dst) {
        List<List<Integer>> graph = new ArrayList<>();
        int[] inDeg = new int[n];
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] e : edges) { graph.get(e[0]).add(e[1]); inDeg[e[1]]++; }

        Queue<Integer> q = new LinkedList<>();
        for (int i = 0; i < n; i++) if (inDeg[i] == 0) q.offer(i);
        List<Integer> order = new ArrayList<>();
        while (!q.isEmpty()) {
            int node = q.poll(); order.add(node);
            for (int nei : graph.get(node)) if (--inDeg[nei] == 0) q.offer(nei);
        }

        int[] paths = new int[n];
        paths[src] = 1;
        for (int node : order)
            for (int nei : graph.get(node))
                paths[nei] += paths[node];
        return paths[dst];
    }

    public static void main(String[] args) {
        Problem33_DAGPathCount solver = new Problem33_DAGPathCount();
        System.out.println(solver.countPaths(5, new int[][]{{0,1},{0,2},{1,3},{2,3},{3,4}}, 0, 4)); // 2
    }
}
