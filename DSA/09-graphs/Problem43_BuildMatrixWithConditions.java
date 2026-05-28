import java.util.*;

/**
 * Problem 43: Build a Matrix With Conditions (LeetCode 2392)
 * 
 * Approach: Topological sort for row conditions and column conditions independently.
 * Place each number at (row_order, col_order) position in k×k matrix.
 * Time: O(k^2 + E), Space: O(k^2)
 * 
 * Production Analogy: Scheduling services on a 2D resource grid with row/column ordering constraints.
 */
public class Problem43_BuildMatrixWithConditions {
    
    public int[][] buildMatrix(int k, int[][] rowConditions, int[][] colConditions) {
        int[] rowOrder = topoSort(k, rowConditions);
        int[] colOrder = topoSort(k, colConditions);
        if (rowOrder == null || colOrder == null) return new int[0][0];
        int[] colPos = new int[k + 1];
        for (int i = 0; i < k; i++) colPos[colOrder[i]] = i;
        int[][] matrix = new int[k][k];
        for (int i = 0; i < k; i++) matrix[i][colPos[rowOrder[i]]] = rowOrder[i];
        return matrix;
    }
    
    int[] topoSort(int k, int[][] conditions) {
        List<Integer>[] adj = new List[k + 1];
        int[] indegree = new int[k + 1];
        for (int i = 0; i <= k; i++) adj[i] = new ArrayList<>();
        for (int[] c : conditions) { adj[c[0]].add(c[1]); indegree[c[1]]++; }
        Queue<Integer> q = new LinkedList<>();
        for (int i = 1; i <= k; i++) if (indegree[i] == 0) q.offer(i);
        int[] order = new int[k]; int idx = 0;
        while (!q.isEmpty()) { int n = q.poll(); order[idx++] = n;
            for (int next : adj[n]) if (--indegree[next] == 0) q.offer(next); }
        return idx == k ? order : null;
    }
    
    public static void main(String[] args) {
        Problem43_BuildMatrixWithConditions sol = new Problem43_BuildMatrixWithConditions();
        int[][] res = sol.buildMatrix(3, new int[][]{{1,2},{3,2}}, new int[][]{{2,1},{3,2}});
        for (int[] row : res) System.out.println(Arrays.toString(row));
        System.out.println("---");
        int[][] res2 = sol.buildMatrix(3, new int[][]{{1,2},{2,3},{3,1},{2,3}}, new int[][]{{2,1}});
        System.out.println("Cycle case: " + res2.length); // 0
    }
}
