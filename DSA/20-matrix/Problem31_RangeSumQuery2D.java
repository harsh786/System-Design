import java.util.*;

/**
 * Problem 31: Range Sum Query 2D - Immutable
 * 
 * Given a 2D matrix, handle multiple queries for sum of elements in a submatrix.
 *
 * Approach: 2D prefix sum. Query in O(1) using inclusion-exclusion.
 * sum(r1,c1,r2,c2) = prefix[r2+1][c2+1] - prefix[r1][c2+1] - prefix[r2+1][c1] + prefix[r1][c1]
 *
 * Time Complexity: O(m*n) preprocessing, O(1) per query
 * Space Complexity: O(m*n)
 *
 * Production Analogy: Pre-computed aggregate tables in OLAP cubes for instant
 * regional sum queries - like total sales in a geographic rectangle.
 */
public class Problem31_RangeSumQuery2D {

    private int[][] prefix;

    public Problem31_RangeSumQuery2D(int[][] matrix) {
        int m = matrix.length, n = matrix[0].length;
        prefix = new int[m+1][n+1];
        for (int i = 1; i <= m; i++)
            for (int j = 1; j <= n; j++)
                prefix[i][j] = matrix[i-1][j-1] + prefix[i-1][j] + prefix[i][j-1] - prefix[i-1][j-1];
    }

    public int sumRegion(int r1, int c1, int r2, int c2) {
        return prefix[r2+1][c2+1] - prefix[r1][c2+1] - prefix[r2+1][c1] + prefix[r1][c1];
    }

    public static void main(String[] args) {
        int[][] matrix = {{3,0,1,4,2},{5,6,3,2,1},{1,2,0,1,5},{4,1,0,1,7},{1,0,3,0,5}};
        Problem31_RangeSumQuery2D obj = new Problem31_RangeSumQuery2D(matrix);
        System.out.println("Test 1: " + obj.sumRegion(2, 1, 4, 3)); // 8
        System.out.println("Test 2: " + obj.sumRegion(1, 1, 2, 2)); // 11
        System.out.println("Test 3: " + obj.sumRegion(1, 2, 2, 4)); // 12
    }
}
