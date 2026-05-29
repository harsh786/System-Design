import java.util.*;

/**
 * Problem 1: Set Matrix Zeroes
 * 
 * Given an m x n matrix, if an element is 0, set its entire row and column to 0.
 * Do it in-place.
 *
 * Approach: Use first row and first column as markers.
 * - First pass: mark which rows/cols need zeroing using first row/col as storage
 * - Second pass: zero out cells based on markers
 * - Finally handle first row/col separately
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(1) - in-place using matrix itself as storage
 *
 * Production Analogy: In image processing, when a dead pixel is detected in a sensor row/column,
 * the entire line may be flagged for interpolation repair. Similar to marking corrupted
 * cache lines in a distributed cache grid.
 */
public class Problem01_SetMatrixZeroes {

    public static void setZeroes(int[][] matrix) {
        int m = matrix.length, n = matrix[0].length;
        boolean firstRowZero = false, firstColZero = false;

        // Check if first row/col have zeros
        for (int j = 0; j < n; j++) if (matrix[0][j] == 0) firstRowZero = true;
        for (int i = 0; i < m; i++) if (matrix[i][0] == 0) firstColZero = true;

        // Use first row/col as markers
        for (int i = 1; i < m; i++)
            for (int j = 1; j < n; j++)
                if (matrix[i][j] == 0) {
                    matrix[i][0] = 0;
                    matrix[0][j] = 0;
                }

        // Zero out based on markers
        for (int i = 1; i < m; i++)
            for (int j = 1; j < n; j++)
                if (matrix[i][0] == 0 || matrix[0][j] == 0)
                    matrix[i][j] = 0;

        // Handle first row/col
        if (firstRowZero) for (int j = 0; j < n; j++) matrix[0][j] = 0;
        if (firstColZero) for (int i = 0; i < m; i++) matrix[i][0] = 0;
    }

    public static void main(String[] args) {
        // Test 1: Basic case
        int[][] m1 = {{1,1,1},{1,0,1},{1,1,1}};
        setZeroes(m1);
        System.out.println("Test 1: " + Arrays.deepToString(m1));
        // Expected: [[1,0,1],[0,0,0],[1,0,1]]

        // Test 2: Multiple zeros
        int[][] m2 = {{0,1,2,0},{3,4,5,2},{1,3,1,5}};
        setZeroes(m2);
        System.out.println("Test 2: " + Arrays.deepToString(m2));
        // Expected: [[0,0,0,0],[0,4,5,0],[0,3,1,0]]

        // Test 3: Single element
        int[][] m3 = {{0}};
        setZeroes(m3);
        System.out.println("Test 3: " + Arrays.deepToString(m3));

        // Test 4: No zeros
        int[][] m4 = {{1,2},{3,4}};
        setZeroes(m4);
        System.out.println("Test 4: " + Arrays.deepToString(m4));
    }
}
