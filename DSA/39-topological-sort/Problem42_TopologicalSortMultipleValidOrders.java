import java.util.*;

/**
 * Problem: Topological Sort Multiple Valid Orders
 * Generate all valid topological orderings.
 *
 * Approach: Backtracking - at each step try all nodes with in-degree 0
 *
 * Time Complexity: O(V! / constraints) worst case
 * Space Complexity: O(V)
 *
 * Production Analogy: Generating all valid migration paths for testing.
 */
public class Problem42_TopologicalSortMultipleValidOrders {

    public List<List<Integer>> allOrders(int n, int[][] edges) {
        List<List<Integer>> graph = new ArrayList<>(), result = new ArrayList<>();
        int[] inDeg = new int[n];
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] e : edges) { graph.get(e[0]).add(e[1]); inDeg[e[1]]++; }

        backtrack(graph, inDeg, n, new ArrayList<>(), result);
        return result;
    }

    private void backtrack(List<List<Integer>> graph, int[] inDeg, int n, List<Integer> path, List<List<Integer>> result) {
        if (path.size() == n) { result.add(new ArrayList<>(path)); return; }
        for (int i = 0; i < n; i++) {
            if (inDeg[i] == 0) {
                path.add(i); inDeg[i] = -1;
                for (int nei : graph.get(i)) inDeg[nei]--;
                backtrack(graph, inDeg, n, path, result);
                path.remove(path.size() - 1); inDeg[i] = 0;
                for (int nei : graph.get(i)) inDeg[nei]++;
            }
        }
    }

    public static void main(String[] args) {
        Problem42_TopologicalSortMultipleValidOrders solver = new Problem42_TopologicalSortMultipleValidOrders();
        System.out.println(solver.allOrders(3, new int[][]{{0,1},{0,2}}));
    }
}
