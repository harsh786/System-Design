import java.util.*;

/**
 * Problem 19: Maximal Rectangle (LeetCode 85)
 * 
 * Given binary matrix, find largest rectangle containing only 1's.
 * 
 * Approach: Build histogram for each row (heights of consecutive 1's above),
 * then apply Largest Rectangle in Histogram for each row.
 * 
 * Time Complexity: O(rows * cols)
 * Space Complexity: O(cols)
 * 
 * Production Analogy: Like finding the largest contiguous block of healthy servers
 * in a data center grid layout for workload placement.
 */
public class Problem19_MaximalRectangle {

    public static int maximalRectangle(char[][] matrix) {
        if (matrix.length == 0) return 0;
        int cols = matrix[0].length;
        int[] heights = new int[cols];
        int maxArea = 0;
        for (char[] row : matrix) {
            for (int j = 0; j < cols; j++) {
                heights[j] = row[j] == '1' ? heights[j] + 1 : 0;
            }
            maxArea = Math.max(maxArea, largestRectangle(heights));
        }
        return maxArea;
    }

    private static int largestRectangle(int[] heights) {
        Deque<Integer> stack = new ArrayDeque<>();
        int max = 0;
        for (int i = 0; i <= heights.length; i++) {
            int h = i == heights.length ? 0 : heights[i];
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
        char[][] m1 = {
            {'1','0','1','0','0'},
            {'1','0','1','1','1'},
            {'1','1','1','1','1'},
            {'1','0','0','1','0'}
        };
        System.out.println(maximalRectangle(m1)); // 6
        System.out.println(maximalRectangle(new char[][]{{'0'}})); // 0
        System.out.println(maximalRectangle(new char[][]{{'1'}})); // 1
    }
}
