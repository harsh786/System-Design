import java.util.*;

public class Problem50_OutOfBoundaryPaths {
    private static final int MOD = 1_000_000_007;
    private Integer[][][] memo;

    public int findPaths(int m, int n, int maxMove, int startRow, int startColumn) {
        memo = new Integer[m][n][maxMove + 1];
        return helper(m, n, maxMove, startRow, startColumn);
    }

    private int helper(int m, int n, int moves, int r, int c) {
        if (r < 0 || r >= m || c < 0 || c >= n) return 1;
        if (moves == 0) return 0;
        if (memo[r][c][moves] != null) return memo[r][c][moves];
        long result = ((long)helper(m,n,moves-1,r-1,c) + helper(m,n,moves-1,r+1,c)
                     + helper(m,n,moves-1,r,c-1) + helper(m,n,moves-1,r,c+1)) % MOD;
        memo[r][c][moves] = (int) result;
        return memo[r][c][moves];
    }

    public static void main(String[] args) {
        Problem50_OutOfBoundaryPaths sol = new Problem50_OutOfBoundaryPaths();
        System.out.println(sol.findPaths(2, 2, 2, 0, 0)); // 6
    }
}
