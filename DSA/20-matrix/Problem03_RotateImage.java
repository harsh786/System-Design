import java.util.*;

/**
 * Problem 3: Rotate Image
 * 
 * Rotate an n x n matrix 90 degrees clockwise in-place.
 *
 * Approach: Transpose the matrix, then reverse each row.
 * - Transpose: swap matrix[i][j] with matrix[j][i]
 * - Reverse rows: reverse each row
 *
 * Time Complexity: O(n^2)
 * Space Complexity: O(1)
 *
 * Production Analogy: Image rotation in photo editors. When rotating a game board
 * (e.g., Tetris piece rotation). Also relevant in display rendering when screen
 * orientation changes (portrait to landscape).
 */
public class Problem03_RotateImage {

    public static void rotate(int[][] matrix) {
        int n = matrix.length;
        // Transpose
        for (int i = 0; i < n; i++)
            for (int j = i + 1; j < n; j++) {
                int tmp = matrix[i][j];
                matrix[i][j] = matrix[j][i];
                matrix[j][i] = tmp;
            }
        // Reverse each row
        for (int i = 0; i < n; i++)
            for (int l = 0, r = n - 1; l < r; l++, r--) {
                int tmp = matrix[i][l];
                matrix[i][l] = matrix[i][r];
                matrix[i][r] = tmp;
            }
    }

    public static void main(String[] args) {
        int[][] m1 = {{1,2,3},{4,5,6},{7,8,9}};
        rotate(m1);
        System.out.println("Test 1: " + Arrays.deepToString(m1));
        // [[7,4,1],[8,5,2],[9,6,3]]

        int[][] m2 = {{5,1,9,11},{2,4,8,10},{13,3,6,7},{15,14,12,16}};
        rotate(m2);
        System.out.println("Test 2: " + Arrays.deepToString(m2));

        int[][] m3 = {{1}};
        rotate(m3);
        System.out.println("Test 3: " + Arrays.deepToString(m3));
    }
}
