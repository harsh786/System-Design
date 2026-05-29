import java.util.*;

public class Problem22_UniquePaths {
    private Integer[][] memo;

    public int uniquePaths(int m, int n) {
        memo = new Integer[m][n];
        return helper(0, 0, m, n);
    }

    private int helper(int i, int j, int m, int n) {
        if (i == m - 1 && j == n - 1) return 1;
        if (i >= m || j >= n) return 0;
        if (memo[i][j] != null) return memo[i][j];
        memo[i][j] = helper(i + 1, j, m, n) + helper(i, j + 1, m, n);
        return memo[i][j];
    }

    public static void main(String[] args) {
        Problem22_UniquePaths sol = new Problem22_UniquePaths();
        System.out.println("uniquePaths(3,7): " + sol.uniquePaths(3, 7)); // 28
    }
}
