import java.util.*;

/**
 * Problem 9: Maximal Rectangle
 * 
 * Find the largest rectangle containing only 1's.
 *
 * Approach: Build histogram heights row by row, apply "largest rectangle in histogram"
 * using a stack for each row.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(n)
 *
 * Production Analogy: Finding the largest contiguous free block in a 2D memory layout,
 * or the biggest rectangular ad placement slot on a webpage grid.
 */
public class Problem09_MaximalRectangle {

    public static int maximalRectangle(char[][] matrix) {
        if (matrix.length == 0) return 0;
        int n = matrix[0].length, maxArea = 0;
        int[] heights = new int[n];
        for (char[] row : matrix) {
            for (int j = 0; j < n; j++)
                heights[j] = row[j] == '1' ? heights[j] + 1 : 0;
            maxArea = Math.max(maxArea, largestInHistogram(heights));
        }
        return maxArea;
    }

    private static int largestInHistogram(int[] heights) {
        Deque<Integer> stack = new ArrayDeque<>();
        int max = 0, n = heights.length;
        for (int i = 0; i <= n; i++) {
            int h = (i == n) ? 0 : heights[i];
            while (!stack.isEmpty() && h < heights[stack.peek()]) {
                int height = heights[stack.pop()];
                int width = stack.isEmpty() ? i : i - stack.peek() - 1;
                max = Math.max(max, height * width);
            }
            stack.push(i);
        }
        return max;
    }

    public static void main(String[] args) {
        char[][] m1 = {{'1','0','1','0','0'},{'1','0','1','1','1'},{'1','1','1','1','1'},{'1','0','0','1','0'}};
        System.out.println("Test 1: " + maximalRectangle(m1)); // 6

        char[][] m2 = {{'0'}};
        System.out.println("Test 2: " + maximalRectangle(m2)); // 0

        char[][] m3 = {{'1'}};
        System.out.println("Test 3: " + maximalRectangle(m3)); // 1

        char[][] m4 = {{'1','1','1'},{'1','1','1'}};
        System.out.println("Test 4: " + maximalRectangle(m4)); // 6
    }
}
