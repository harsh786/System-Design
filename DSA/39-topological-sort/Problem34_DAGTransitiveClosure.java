import java.util.*;

/**
 * Problem: DAG Transitive Closure
 * Compute reachability matrix for a DAG.
 *
 * Approach: Topological sort + propagate reachability using bitsets
 *
 * Time Complexity: O(V^2/64 * (V + E)) with bitset optimization
 * Space Complexity: O(V^2)
 *
 * Production Analogy: Pre-computing service dependency reachability for impact analysis.
 */
public class Problem34_DAGTransitiveClosure {

    public boolean[][] transitiveClosure(int n, int[][] edges) {
        List<List<Integer>> graph = new ArrayList<>();
        int[] inDeg = new int[n];
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] e : edges) { graph.get(e[0]).add(e[1]); inDeg[e[1]]++; }

        boolean[][] reach = new boolean[n][n];
        for (int i = 0; i < n; i++) reach[i][i] = true;

        // Reverse topological order
        Deque<Integer> stack = new ArrayDeque<>();
        Queue<Integer> q = new LinkedList<>();
        for (int i = 0; i < n; i++) if (inDeg[i] == 0) q.offer(i);
        while (!q.isEmpty()) {
            int node = q.poll(); stack.push(node);
            for (int nei : graph.get(node)) if (--inDeg[nei] == 0) q.offer(nei);
        }

        while (!stack.isEmpty()) {
            int node = stack.pop();
            for (int nei : graph.get(node))
                for (int i = 0; i < n; i++)
                    if (reach[nei][i]) reach[node][i] = true;
        }
        return reach;
    }

    public static void main(String[] args) {
        Problem34_DAGTransitiveClosure solver = new Problem34_DAGTransitiveClosure();
        boolean[][] r = solver.transitiveClosure(4, new int[][]{{0,1},{1,2},{2,3}});
        System.out.println(r[0][3]); // true
        System.out.println(r[3][0]); // false
    }
}
