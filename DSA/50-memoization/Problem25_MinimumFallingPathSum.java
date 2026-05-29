import java.util.*;

public class Problem25_MinimumFallingPathSum {
    private Integer[][] memo;

    public int minFallingPathSum(int[][] matrix) {
        int n = matrix.length;
        memo = new Integer[n][n];
        int min = Integer.MAX_VALUE;
        for (int col = 0; col < n; col++) min = Math.min(min, helper(matrix, 0, col));
        return min;
    }

    private int helper(int[][] m, int r, int c) {
        if (c < 0 || c >= m.length) return Integer.MAX_VALUE;
        if (r == m.length - 1) return m[r][c];
        if (memo[r][c] != null) return memo[r][c];
        memo[r][c] = m[r][c] + Math.min(helper(m, r+1, c), Math.min(helper(m, r+1, c-1), helper(m, r+1, c+1)));
        return memo[r][c];
    }

    public static void main(String[] args) {
        Problem25_MinimumFallingPathSum sol = new Problem25_MinimumFallingPathSum();
        System.out.println(sol.minFallingPathSum(new int[][]{{2,1,3},{6,5,4},{7,8,9}})); // 13
    }
}
