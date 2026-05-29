import java.util.*;

public class Problem15_NumberOfSquarefulArrays {
    public int numSquarefulPerms(int[] nums) {
        int n = nums.length;
        Arrays.sort(nums);
        int[][] dp = new int[1 << n][n];
        for (int i = 0; i < n; i++) { if (i > 0 && nums[i] == nums[i-1]) continue; dp[1 << i][i] = 1; }
        for (int mask = 0; mask < (1 << n); mask++)
            for (int last = 0; last < n; last++) {
                if (dp[mask][last] == 0) continue;
                for (int next = 0; next < n; next++) {
                    if ((mask & (1 << next)) != 0) continue;
                    if (next > 0 && nums[next] == nums[next-1] && (mask & (1 << (next-1))) == 0) continue;
                    int s = (int) Math.round(Math.sqrt(nums[last] + nums[next]));
                    if (s * s == nums[last] + nums[next]) dp[mask | (1 << next)][next] += dp[mask][last];
                }
            }
        int result = 0;
        for (int i = 0; i < n; i++) result += dp[(1 << n) - 1][i];
        return result;
    }

    public static void main(String[] args) {
        System.out.println(new Problem15_NumberOfSquarefulArrays().numSquarefulPerms(new int[]{1,17,8}));
    }
}
