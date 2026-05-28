/**
 * Problem 39: Score After Flipping Matrix (LeetCode 861)
 *
 * Greedy Choice: Ensure MSB of each row is 1 (flip row if needed). 
 * Then for each column, maximize 1s (flip column if more 0s).
 *
 * Time: O(m*n), Space: O(1)
 *
 * Production Analogy: Maximizing binary-encoded priority values by toggling feature flags.
 */
public class Problem39_ScoreAfterFlippingMatrix {
    
    public static int matrixScore(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        // Flip rows to ensure first column is all 1s
        for (int i = 0; i < m; i++) {
            if (grid[i][0] == 0) {
                for (int j = 0; j < n; j++) grid[i][j] ^= 1;
            }
        }
        // Flip columns if more 0s than 1s
        for (int j = 1; j < n; j++) {
            int ones = 0;
            for (int i = 0; i < m; i++) ones += grid[i][j];
            if (ones < m - ones) {
                for (int i = 0; i < m; i++) grid[i][j] ^= 1;
            }
        }
        int score = 0;
        for (int[] row : grid) {
            int val = 0;
            for (int bit : row) val = val * 2 + bit;
            score += val;
        }
        return score;
    }
    
    public static void main(String[] args) {
        System.out.println(matrixScore(new int[][]{{0,0,1,1},{1,0,1,0},{1,1,0,0}})); // 39
        System.out.println(matrixScore(new int[][]{{0}})); // 1
    }
}
