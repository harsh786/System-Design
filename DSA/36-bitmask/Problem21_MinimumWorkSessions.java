import java.util.Arrays;

public class Problem21_MinimumWorkSessions {
    public int minSessions(int[] tasks, int sessionTime) {
        int n = tasks.length;
        int[] subsetTime = new int[1 << n];
        for (int mask = 1; mask < (1 << n); mask++) {
            int lsb = mask & -mask;
            subsetTime[mask] = subsetTime[mask ^ lsb] + tasks[Integer.numberOfTrailingZeros(lsb)];
        }
        int[] dp = new int[1 << n];
        Arrays.fill(dp, n);
        dp[0] = 0;
        for (int mask = 1; mask < (1 << n); mask++) {
            for (int sub = mask; sub > 0; sub = (sub - 1) & mask) {
                if (subsetTime[sub] <= sessionTime) dp[mask] = Math.min(dp[mask], dp[mask ^ sub] + 1);
            }
        }
        return dp[(1 << n) - 1];
    }

    public static void main(String[] args) {
        System.out.println(new Problem21_MinimumWorkSessions().minSessions(new int[]{1,2,3,4,5}, 15));
    }
}
