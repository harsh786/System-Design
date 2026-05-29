import java.util.*;

/**
 * Problem: Build Matrix With Conditions
 * Build k x k matrix placing 1..k with row and column ordering conditions.
 *
 * Approach: Two independent topological sorts for row order and column order
 *
 * Time Complexity: O(k + conditions)
 * Space Complexity: O(k^2)
 *
 * Production Analogy: Placing services in a deployment matrix respecting both
 * horizontal and vertical dependency constraints.
 */
public class Problem10_BuildMatrixWithConditions {

    public int[][] buildMatrix(int k, int[][] rowConditions, int[][] colConditions) {
        List<Integer> rowOrder = topoSort(k, rowConditions);
        List<Integer> colOrder = topoSort(k, colConditions);
        if (rowOrder.isEmpty() || colOrder.isEmpty()) return new int[0][0];

        int[] rowPos = new int[k + 1], colPos = new int[k + 1];
        for (int i = 0; i < k; i++) { rowPos[rowOrder.get(i)] = i; colPos[colOrder.get(i)] = i; }

        int[][] matrix = new int[k][k];
        for (int i = 1; i <= k; i++) matrix[rowPos[i]][colPos[i]] = i;
        return matrix;
    }

    private List<Integer> topoSort(int k, int[][] conditions) {
        List<List<Integer>> g = new ArrayList<>();
        int[] inDeg = new int[k + 1];
        for (int i = 0; i <= k; i++) g.add(new ArrayList<>());
        for (int[] c : conditions) { g.get(c[0]).add(c[1]); inDeg[c[1]]++; }

        Queue<Integer> q = new LinkedList<>();
        for (int i = 1; i <= k; i++) if (inDeg[i] == 0) q.offer(i);
        List<Integer> order = new ArrayList<>();
        while (!q.isEmpty()) {
            int node = q.poll(); order.add(node);
            for (int nei : g.get(node)) if (--inDeg[nei] == 0) q.offer(nei);
        }
        return order.size() == k ? order : Collections.emptyList();
    }

    public static void main(String[] args) {
        Problem10_BuildMatrixWithConditions solver = new Problem10_BuildMatrixWithConditions();
        int[][] res = solver.buildMatrix(3, new int[][]{{1,2},{3,2}}, new int[][]{{2,1},{3,2}});
        for (int[] row : res) System.out.println(Arrays.toString(row));
    }
}
