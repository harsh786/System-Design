import java.util.*;

public class Problem39_NumberOfDiceRollsWithTargetSum {
    private static final int MOD = 1_000_000_007;
    private Integer[][] memo;

    public int numRollsToTarget(int n, int k, int target) {
        memo = new Integer[n + 1][target + 1];
        return helper(n, k, target);
    }

    private int helper(int n, int k, int target) {
        if (n == 0) return target == 0 ? 1 : 0;
        if (target <= 0) return 0;
        if (memo[n][target] != null) return memo[n][target];
        long sum = 0;
        for (int face = 1; face <= k; face++) sum = (sum + helper(n - 1, k, target - face)) % MOD;
        memo[n][target] = (int) sum;
        return memo[n][target];
    }

    public static void main(String[] args) {
        Problem39_NumberOfDiceRollsWithTargetSum sol = new Problem39_NumberOfDiceRollsWithTargetSum();
        System.out.println(sol.numRollsToTarget(2, 6, 7)); // 6
    }
}
