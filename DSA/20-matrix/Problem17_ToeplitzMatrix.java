import java.util.*;

/**
 * Problem 17: Toeplitz Matrix
 * 
 * A matrix is Toeplitz if every diagonal from top-left to bottom-right has same elements.
 *
 * Approach: Check each element equals its top-left neighbor: matrix[i][j] == matrix[i-1][j-1]
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(1)
 *
 * Production Analogy: Toeplitz matrices appear in signal processing (convolution),
 * time-invariant systems, and efficient matrix-vector multiplication in DSP hardware.
 */
public class Problem17_ToeplitzMatrix {

    public static boolean isToeplitzMatrix(int[][] matrix) {
        for (int i = 1; i < matrix.length; i++)
            for (int j = 1; j < matrix[0].length; j++)
                if (matrix[i][j] != matrix[i-1][j-1]) return false;
        return true;
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + isToeplitzMatrix(new int[][]{{1,2,3,4},{5,1,2,3},{9,5,1,2}})); // true
        System.out.println("Test 2: " + isToeplitzMatrix(new int[][]{{1,2},{2,2}})); // false
    }
}
