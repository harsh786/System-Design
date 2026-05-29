import java.util.*;

public class Problem36_KnightDialer {
    private static final int MOD = 1_000_000_007;
    private static final int[][] moves = {{4,6},{6,8},{7,9},{4,8},{0,3,9},{},{0,1,7},{2,6},{1,3},{2,4}};
    private Integer[][] memo;

    public int knightDialer(int n) {
        memo = new Integer[n + 1][10];
        long sum = 0;
        for (int d = 0; d <= 9; d++) sum = (sum + helper(n, d)) % MOD;
        return (int) sum;
    }

    private int helper(int remaining, int digit) {
        if (remaining == 1) return 1;
        if (memo[remaining][digit] != null) return memo[remaining][digit];
        long sum = 0;
        for (int next : moves[digit]) sum = (sum + helper(remaining - 1, next)) % MOD;
        memo[remaining][digit] = (int) sum;
        return memo[remaining][digit];
    }

    public static void main(String[] args) {
        Problem36_KnightDialer sol = new Problem36_KnightDialer();
        System.out.println("Knight Dialer n=3: " + sol.knightDialer(3)); // 46
    }
}
