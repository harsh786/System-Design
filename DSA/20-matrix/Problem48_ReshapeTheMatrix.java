import java.util.*;

/**
 * Problem 48: Reshape the Matrix
 * 
 * Reshape m x n matrix to r x c. If not possible, return original.
 *
 * Approach: Check if m*n == r*c. Map linear index to 2D coordinates in both shapes.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(r * c)
 *
 * Production Analogy: Reshaping tensor data between different layer dimensions in
 * neural network inference - ensuring total element count matches.
 */
public class Problem48_ReshapeTheMatrix {

    public static int[][] matrixReshape(int[][] mat, int r, int c) {
        int m = mat.length, n = mat[0].length;
        if (m * n != r * c) return mat;
        int[][] result = new int[r][c];
        for (int i = 0; i < m * n; i++)
            result[i / c][i % c] = mat[i / n][i % n];
        return result;
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + Arrays.deepToString(matrixReshape(new int[][]{{1,2},{3,4}}, 1, 4)));
        // [[1,2,3,4]]
        System.out.println("Test 2: " + Arrays.deepToString(matrixReshape(new int[][]{{1,2},{3,4}}, 2, 4)));
        // [[1,2],[3,4]] (impossible)
    }
}
