import java.util.*;

/**
 * Problem 46: Spiral Matrix II
 * 
 * Generate n x n matrix filled with elements 1 to n^2 in spiral order.
 *
 * Approach: Same boundary technique as Spiral Matrix I, but fill instead of read.
 *
 * Time Complexity: O(n^2)
 * Space Complexity: O(n^2) for output
 *
 * Production Analogy: Generating sequential IDs in a spatial layout - like assigning
 * seat numbers in a spiral seating arrangement for an event.
 */
public class Problem46_SpiralMatrixII {

    public static int[][] generateMatrix(int n) {
        int[][] matrix = new int[n][n];
        int top = 0, bottom = n-1, left = 0, right = n-1, num = 1;
        while (top <= bottom && left <= right) {
            for (int j = left; j <= right; j++) matrix[top][j] = num++;
            top++;
            for (int i = top; i <= bottom; i++) matrix[i][right] = num++;
            right--;
            for (int j = right; j >= left; j--) matrix[bottom][j] = num++;
            bottom--;
            for (int i = bottom; i >= top; i--) matrix[i][left] = num++;
            left++;
        }
        return matrix;
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + Arrays.deepToString(generateMatrix(3)));
        // [[1,2,3],[8,9,4],[7,6,5]]
        System.out.println("Test 2: " + Arrays.deepToString(generateMatrix(1)));
        System.out.println("Test 3: " + Arrays.deepToString(generateMatrix(4)));
    }
}
