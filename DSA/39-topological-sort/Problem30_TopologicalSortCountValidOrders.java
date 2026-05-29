import java.util.*;

/**
 * Problem: Topological Sort Count Valid Orders
 * Count all valid topological orderings of a DAG.
 *
 * Approach: Backtracking with in-degree tracking
 *
 * Time Complexity: O(V! / (product of constraints)) worst case
 * Space Complexity: O(V)
 *
 * Production Analogy: Counting possible deployment sequences for risk assessment.
 */
public class Problem30_TopologicalSortCountValidOrders {

    private int count;

    public int countOrders(int n, int[][] edges) {
        List<List<Integer>> graph = new ArrayList<>();
        int[] inDeg = new int[n];
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] e : edges) { graph.get(e[0]).add(e[1]); inDeg[e[1]]++; }

        count = 0;
        backtrack(graph, inDeg, n, 0);
        return count;
    }

    private void backtrack(List<List<Integer>> graph, int[] inDeg, int n, int depth) {
        if (depth == n) { count++; return; }
        for (int i = 0; i < n; i++) {
            if (inDeg[i] == 0) {
                inDeg[i] = -1;
                for (int nei : graph.get(i)) inDeg[nei]--;
                backtrack(graph, inDeg, n, depth + 1);
                inDeg[i] = 0;
                for (int nei : graph.get(i)) inDeg[nei]++;
            }
        }
    }

    public static void main(String[] args) {
        Problem30_TopologicalSortCountValidOrders solver = new Problem30_TopologicalSortCountValidOrders();
        System.out.println(solver.countOrders(4, new int[][]{{0,1},{1,2}})); // 4! / constraints
    }
}
