import java.util.*;

/**
 * Problem 45: Equal Row and Column Pairs
 * Count pairs (r, c) where row r equals column c in an n x n grid.
 *
 * Approach: Hash each row as a string key, store counts. Then hash each column and look up.
 *
 * Time Complexity: O(n^2)
 * Space Complexity: O(n^2)
 *
 * Production Analogy: Like finding symmetric relationships in a correlation matrix
 * for feature selection in ML pipelines.
 */
public class Problem45_EqualRowAndColumnPairs {
    public int equalPairs(int[][] grid) {
        int n = grid.length;
        Map<String, Integer> rowMap = new HashMap<>();
        for (int[] row : grid) rowMap.merge(Arrays.toString(row), 1, Integer::sum);
        int count = 0;
        for (int c = 0; c < n; c++) {
            int[] col = new int[n];
            for (int r = 0; r < n; r++) col[r] = grid[r][c];
            count += rowMap.getOrDefault(Arrays.toString(col), 0);
        }
        return count;
    }

    public static void main(String[] args) {
        Problem45_EqualRowAndColumnPairs sol = new Problem45_EqualRowAndColumnPairs();
        System.out.println(sol.equalPairs(new int[][]{{3,2,1},{1,7,6},{2,7,7}})); // 1
        System.out.println(sol.equalPairs(new int[][]{{3,1,2,2},{1,4,4,5},{2,4,2,2},{2,4,2,2}})); // 3
    }
}
