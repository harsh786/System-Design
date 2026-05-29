import java.util.*;

/**
 * Problem: Topological Sort with Cycle Reporting
 * If cycle exists, report the nodes in the cycle.
 *
 * Approach: DFS with parent tracking to reconstruct cycle path
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V)
 *
 * Production Analogy: Providing actionable error messages when circular dependencies detected.
 */
public class Problem41_TopologicalSortWithCycleReporting {

    public List<Integer> findCycle(int n, int[][] edges) {
        List<List<Integer>> graph = new ArrayList<>();
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] e : edges) graph.get(e[0]).add(e[1]);

        int[] color = new int[n], parent = new int[n];
        Arrays.fill(parent, -1);

        for (int i = 0; i < n; i++) {
            if (color[i] == 0) {
                List<Integer> cycle = dfs(graph, i, color, parent);
                if (cycle != null) return cycle;
            }
        }
        return Collections.emptyList();
    }

    private List<Integer> dfs(List<List<Integer>> graph, int node, int[] color, int[] parent) {
        color[node] = 1;
        for (int nei : graph.get(node)) {
            if (color[nei] == 1) {
                List<Integer> cycle = new ArrayList<>();
                int cur = node;
                while (cur != nei) { cycle.add(cur); cur = parent[cur]; }
                cycle.add(nei);
                Collections.reverse(cycle);
                return cycle;
            }
            if (color[nei] == 0) {
                parent[nei] = node;
                List<Integer> cycle = dfs(graph, nei, color, parent);
                if (cycle != null) return cycle;
            }
        }
        color[node] = 2;
        return null;
    }

    public static void main(String[] args) {
        Problem41_TopologicalSortWithCycleReporting solver = new Problem41_TopologicalSortWithCycleReporting();
        System.out.println(solver.findCycle(4, new int[][]{{0,1},{1,2},{2,0},{2,3}})); // [0,1,2]
    }
}
