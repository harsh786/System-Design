/**
 * Problem: Equal Row and Column Pairs (LeetCode 2352)
 * Approach: Hash rows, compare with columns
 * Complexity: O(n^2) time, O(n^2) space
 * Production Analogy: Cross-dimensional correlation in matrix data warehouses
 */
import java.util.*;
public class Problem23_EqualRowAndColumnPairs {
    public int equalPairs(int[][] grid) {
        int n = grid.length;
        Map<String, Integer> rowMap = new HashMap<>();
        for (int[] row : grid) rowMap.merge(Arrays.toString(row), 1, Integer::sum);
        int count = 0;
        for (int j = 0; j < n; j++) {
            int[] col = new int[n];
            for (int i = 0; i < n; i++) col[i] = grid[i][j];
            count += rowMap.getOrDefault(Arrays.toString(col), 0);
        }
        return count;
    }
    public static void main(String[] args) {
        System.out.println(new Problem23_EqualRowAndColumnPairs().equalPairs(
            new int[][]{{3,2,1},{1,7,6},{2,7,7}})); // 1
    }
}
