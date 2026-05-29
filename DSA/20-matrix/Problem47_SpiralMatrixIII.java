import java.util.*;

/**
 * Problem 47: Spiral Matrix III
 * 
 * Start at (rStart, cStart) in an rows x cols grid, walk in spiral clockwise.
 * Return coordinates in order visited.
 *
 * Approach: Simulate spiral walk. Increase step count every 2 direction changes.
 * Record positions that fall within grid bounds.
 *
 * Time Complexity: O(max(rows, cols)^2)
 * Space Complexity: O(rows * cols)
 *
 * Production Analogy: Expanding search radius from a starting point - like a drone
 * searching for a target in expanding spiral pattern from last known location.
 */
public class Problem47_SpiralMatrixIII {

    public static int[][] spiralMatrixIII(int rows, int cols, int rStart, int cStart) {
        int[][] result = new int[rows * cols][2];
        int idx = 0, r = rStart, c = cStart;
        int[][] dirs = {{0,1},{1,0},{0,-1},{-1,0}}; // right, down, left, up
        int steps = 1, d = 0;
        result[idx++] = new int[]{r, c};
        while (idx < rows * cols) {
            for (int twice = 0; twice < 2; twice++) {
                for (int s = 0; s < steps; s++) {
                    r += dirs[d][0]; c += dirs[d][1];
                    if (r >= 0 && r < rows && c >= 0 && c < cols)
                        result[idx++] = new int[]{r, c};
                }
                d = (d + 1) % 4;
            }
            steps++;
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + Arrays.deepToString(spiralMatrixIII(1, 4, 0, 0)));
        // [[0,0],[0,1],[0,2],[0,3]]
        System.out.println("Test 2: " + Arrays.deepToString(spiralMatrixIII(5, 6, 1, 4)));
    }
}
