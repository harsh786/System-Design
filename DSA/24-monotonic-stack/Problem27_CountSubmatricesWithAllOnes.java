import java.util.*;

/**
 * Problem 27: Count Submatrices With All Ones (LeetCode 1504)
 * 
 * Count number of submatrices that are all 1's.
 * 
 * Approach: Build histogram per row. For each row, use monotonic stack to count
 * rectangles. For each bar, count rectangles where it's the shortest.
 * 
 * Time: O(rows * cols), Space: O(cols)
 * 
 * Production Analogy: Counting valid contiguous resource blocks in a grid
 * allocation system.
 */
public class Problem27_CountSubmatricesWithAllOnes {
    
    public int numSubmat(int[][] mat) {
        int m = mat.length, n = mat[0].length;
        int[] heights = new int[n];
        int total = 0;
        
        for (int i = 0; i < m; i++) {
            for (int j = 0; j < n; j++) {
                heights[j] = mat[i][j] == 1 ? heights[j] + 1 : 0;
            }
            total += countFromHistogram(heights);
        }
        return total;
    }
    
    private int countFromHistogram(int[] heights) {
        int n = heights.length;
        int[] sum = new int[n]; // sum[i] = number of rectangles ending at column i
        Deque<Integer> stack = new ArrayDeque<>();
        
        for (int i = 0; i < n; i++) {
            while (!stack.isEmpty() && heights[stack.peek()] >= heights[i]) stack.pop();
            if (stack.isEmpty()) {
                sum[i] = heights[i] * (i + 1);
            } else {
                sum[i] = sum[stack.peek()] + heights[i] * (i - stack.peek());
            }
            stack.push(i);
        }
        
        int total = 0;
        for (int s : sum) total += s;
        return total;
    }
    
    public static void main(String[] args) {
        Problem27_CountSubmatricesWithAllOnes sol = new Problem27_CountSubmatricesWithAllOnes();
        
        System.out.println(sol.numSubmat(new int[][]{{1,0,1},{1,1,0},{1,1,0}})); // 13
        System.out.println(sol.numSubmat(new int[][]{{0,1,1,0},{0,1,1,1},{1,1,1,0}})); // 24
    }
}
