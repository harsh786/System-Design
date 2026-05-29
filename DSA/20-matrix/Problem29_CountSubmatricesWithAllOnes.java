import java.util.*;

/**
 * Problem 29: Count Submatrices With All Ones
 * 
 * Count number of submatrices that have all ones.
 *
 * Approach: For each cell as bottom-right corner, compute histogram heights
 * and count valid submatrices using stack-based approach or simpler O(n^2) per row.
 * Simpler: for each row, build heights, then for each (i,j) count min-width rectangles.
 *
 * Time Complexity: O(m * n^2) for simple approach, O(m * n) with stack
 * Space Complexity: O(n)
 *
 * Production Analogy: Counting contiguous available resource blocks in a scheduling grid.
 */
public class Problem29_CountSubmatricesWithAllOnes {

    public static int numSubmat(int[][] mat) {
        int m = mat.length, n = mat[0].length, count = 0;
        int[] heights = new int[n];
        for (int i = 0; i < m; i++) {
            for (int j = 0; j < n; j++)
                heights[j] = mat[i][j] == 1 ? heights[j] + 1 : 0;
            // For each column j, count submatrices ending at row i with right edge at j
            for (int j = 0; j < n; j++) {
                int minH = heights[j];
                for (int k = j; k >= 0 && minH > 0; k--) {
                    minH = Math.min(minH, heights[k]);
                    count += minH;
                }
            }
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + numSubmat(new int[][]{{1,0,1},{1,1,0},{1,1,0}})); // 13
        System.out.println("Test 2: " + numSubmat(new int[][]{{0,1,1,0},{0,1,1,1},{1,1,1,0}})); // 24
    }
}
