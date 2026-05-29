/**
 * Problem 2: Range Sum Query 2D - Immutable (LeetCode 304)
 * 
 * Pattern: 2D prefix sum using inclusion-exclusion principle
 * 
 * prefix[i][j] = sum of all elements in rectangle (0,0) to (i-1,j-1)
 * regionSum(r1,c1,r2,c2) = prefix[r2+1][c2+1] - prefix[r1][c2+1] - prefix[r2+1][c1] + prefix[r1][c1]
 * 
 * Time: O(m*n) build, O(1) per query
 * Space: O(m*n)
 * 
 * Production Analogy: Heatmap aggregation in geo-analytics. Computing total orders
 * in a rectangular geo-region uses 2D prefix sums over grid cells.
 */
public class Problem02_RangeSumQuery2D {

    static class NumMatrix {
        private int[][] prefix;

        public NumMatrix(int[][] matrix) {
            int m = matrix.length, n = matrix[0].length;
            prefix = new int[m + 1][n + 1];
            for (int i = 0; i < m; i++)
                for (int j = 0; j < n; j++)
                    prefix[i + 1][j + 1] = matrix[i][j] + prefix[i][j + 1] + prefix[i + 1][j] - prefix[i][j];
        }

        public int sumRegion(int r1, int c1, int r2, int c2) {
            return prefix[r2 + 1][c2 + 1] - prefix[r1][c2 + 1] - prefix[r2 + 1][c1] + prefix[r1][c1];
        }
    }

    public static void main(String[] args) {
        int[][] matrix = {
            {3, 0, 1, 4, 2},
            {5, 6, 3, 2, 1},
            {1, 2, 0, 1, 5},
            {4, 1, 0, 1, 7},
            {1, 0, 3, 0, 5}
        };
        NumMatrix nm = new NumMatrix(matrix);
        assert nm.sumRegion(2, 1, 4, 3) == 8 : "Test 1 failed";
        assert nm.sumRegion(1, 1, 2, 2) == 11 : "Test 2 failed";
        assert nm.sumRegion(1, 2, 2, 4) == 12 : "Test 3 failed";
        assert nm.sumRegion(0, 0, 0, 0) == 3 : "Test 4 failed";
        System.out.println("All tests passed!");
    }
}
