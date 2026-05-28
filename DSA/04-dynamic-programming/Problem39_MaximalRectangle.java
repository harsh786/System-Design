/**
 * Problem 39: Maximal Rectangle
 * 
 * Find largest rectangle containing only 1s in binary matrix.
 * 
 * Approach: For each row, compute histogram heights, then apply largest rectangle in histogram.
 * 
 * Time: O(m*n), Space: O(n)
 */
import java.util.*;

public class Problem39_MaximalRectangle {

    public static int maximalRectangle(char[][] matrix) {
        if (matrix.length == 0) return 0;
        int n = matrix[0].length, max = 0;
        int[] heights = new int[n];
        for (char[] row : matrix) {
            for (int j = 0; j < n; j++) {
                heights[j] = row[j] == '1' ? heights[j] + 1 : 0;
            }
            max = Math.max(max, largestRectangle(heights));
        }
        return max;
    }

    private static int largestRectangle(int[] heights) {
        Deque<Integer> stack = new ArrayDeque<>();
        int max = 0, n = heights.length;
        for (int i = 0; i <= n; i++) {
            int h = i == n ? 0 : heights[i];
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
        System.out.println("=== Maximal Rectangle ===");
        char[][] matrix = {
            {'1','0','1','0','0'},
            {'1','0','1','1','1'},
            {'1','1','1','1','1'},
            {'1','0','0','1','0'}
        };
        System.out.println(maximalRectangle(matrix)); // 6
    }
}
