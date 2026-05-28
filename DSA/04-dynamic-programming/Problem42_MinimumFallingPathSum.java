/**
 * Problem 42: Minimum Falling Path Sum
 * 
 * Fall through matrix choosing one element per row, adjacent column to previous.
 * 
 * State: dp[j] = min falling path sum ending at column j in current row
 * Time: O(m*n), Space: O(n)
 */
public class Problem42_MinimumFallingPathSum {

    public static int minFallingPathSum(int[][] matrix) {
        int n = matrix.length;
        int[] dp = matrix[0].clone();
        for (int i = 1; i < n; i++) {
            int[] newDp = new int[n];
            for (int j = 0; j < n; j++) {
                int best = dp[j];
                if (j > 0) best = Math.min(best, dp[j - 1]);
                if (j < n - 1) best = Math.min(best, dp[j + 1]);
                newDp[j] = matrix[i][j] + best;
            }
            dp = newDp;
        }
        int min = Integer.MAX_VALUE;
        for (int v : dp) min = Math.min(min, v);
        return min;
    }

    public static void main(String[] args) {
        System.out.println("=== Minimum Falling Path Sum ===");
        System.out.println(minFallingPathSum(new int[][]{{2,1,3},{6,5,4},{7,8,9}})); // 13
        System.out.println(minFallingPathSum(new int[][]{{-19,57},{-40,-5}})); // -59
    }
}
