import java.util.*;

/**
 * Problem 2: Spiral Matrix
 * 
 * Given an m x n matrix, return all elements in spiral order.
 *
 * Approach: Use four boundaries (top, bottom, left, right) and shrink them inward.
 * Traverse right, down, left, up in sequence.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(1) extra (output doesn't count)
 *
 * Production Analogy: Similar to how a plotter or CNC machine traverses a rectangular
 * workspace in a spiral pattern to minimize tool head movement. Also used in cache-oblivious
 * matrix traversal for better spatial locality.
 */
public class Problem02_SpiralMatrix {

    public static List<Integer> spiralOrder(int[][] matrix) {
        List<Integer> result = new ArrayList<>();
        if (matrix.length == 0) return result;
        int top = 0, bottom = matrix.length - 1, left = 0, right = matrix[0].length - 1;

        while (top <= bottom && left <= right) {
            for (int j = left; j <= right; j++) result.add(matrix[top][j]);
            top++;
            for (int i = top; i <= bottom; i++) result.add(matrix[i][right]);
            right--;
            if (top <= bottom) {
                for (int j = right; j >= left; j--) result.add(matrix[bottom][j]);
                bottom--;
            }
            if (left <= right) {
                for (int i = bottom; i >= top; i--) result.add(matrix[i][left]);
                left++;
            }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + spiralOrder(new int[][]{{1,2,3},{4,5,6},{7,8,9}}));
        // [1,2,3,6,9,8,7,4,5]
        System.out.println("Test 2: " + spiralOrder(new int[][]{{1,2,3,4},{5,6,7,8},{9,10,11,12}}));
        // [1,2,3,4,8,12,11,10,9,5,6,7]
        System.out.println("Test 3: " + spiralOrder(new int[][]{{1}}));
        System.out.println("Test 4: " + spiralOrder(new int[][]{{1,2,3}}));
        System.out.println("Test 5: " + spiralOrder(new int[][]{{1},{2},{3}}));
    }
}
