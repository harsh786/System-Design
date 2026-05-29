import java.util.Arrays;

public class Problem12_MatchsticksToSquare {
    public boolean makesquare(int[] matchsticks) {
        int sum = Arrays.stream(matchsticks).sum();
        if (sum % 4 != 0) return false;
        int side = sum / 4, n = matchsticks.length;
        int[] dp = new int[1 << n];
        Arrays.fill(dp, -1);
        dp[0] = 0;
        for (int mask = 0; mask < (1 << n); mask++) {
            if (dp[mask] == -1) continue;
            for (int i = 0; i < n; i++) {
                if ((mask & (1 << i)) != 0) continue;
                if (dp[mask] + matchsticks[i] <= side) {
                    dp[mask | (1 << i)] = (dp[mask] + matchsticks[i]) % side;
                }
            }
        }
        return dp[(1 << n) - 1] == 0;
    }

    public static void main(String[] args) {
        System.out.println(new Problem12_MatchsticksToSquare().makesquare(new int[]{1,1,2,2,2}));
    }
}
