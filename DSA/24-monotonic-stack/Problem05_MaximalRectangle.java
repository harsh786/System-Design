import java.util.*;

/**
 * Problem 5: Maximal Rectangle (LeetCode 85)
 * 
 * Find the largest rectangle containing only 1's in a binary matrix.
 * 
 * Approach: Build histogram row by row, apply largest rectangle in histogram.
 * Monotonic Invariant: Same as Problem 4 - increasing stack per row histogram.
 * 
 * Time: O(rows * cols), Space: O(cols)
 * 
 * Production Analogy: Like finding the largest contiguous block of healthy
 * servers in a data center grid layout.
 */
public class Problem05_MaximalRectangle {
    
    public int maximalRectangle(char[][] matrix) {
        if (matrix.length == 0) return 0;
        int cols = matrix[0].length;
        int[] heights = new int[cols];
        int maxArea = 0;
        
        for (char[] row : matrix) {
            for (int j = 0; j < cols; j++) {
                heights[j] = row[j] == '1' ? heights[j] + 1 : 0;
            }
            maxArea = Math.max(maxArea, largestRectangleArea(heights));
        }
        return maxArea;
    }
    
    private int largestRectangleArea(int[] heights) {
        Deque<Integer> stack = new ArrayDeque<>();
        int max = 0;
        for (int i = 0; i <= heights.length; i++) {
            int h = (i == heights.length) ? 0 : heights[i];
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
        Problem05_MaximalRectangle sol = new Problem05_MaximalRectangle();
        
        char[][] matrix1 = {
            {'1','0','1','0','0'},
            {'1','0','1','1','1'},
            {'1','1','1','1','1'},
            {'1','0','0','1','0'}
        };
        System.out.println(sol.maximalRectangle(matrix1)); // 6
        
        char[][] matrix2 = {{'0'}};
        System.out.println(sol.maximalRectangle(matrix2)); // 0
        
        char[][] matrix3 = {{'1'}};
        System.out.println(sol.maximalRectangle(matrix3)); // 1
        
        char[][] matrix4 = {{'1','1'},{'1','1'}};
        System.out.println(sol.maximalRectangle(matrix4)); // 4
    }
}
