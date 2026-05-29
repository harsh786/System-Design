import java.util.*;

public class Problem05_NumberOfLongestIncreasingSubsequence {
    public int findNumberOfLIS(int[] nums) {
        int n = nums.length;
        int[] dp = new int[n], cnt = new int[n];
        int maxLen = 0;
        for (int i = 0; i < n; i++) {
            dp[i] = 1; cnt[i] = 1;
            for (int j = 0; j < i; j++) {
                if (nums[j] < nums[i]) {
                    if (dp[j] + 1 > dp[i]) { dp[i] = dp[j] + 1; cnt[i] = cnt[j]; }
                    else if (dp[j] + 1 == dp[i]) cnt[i] += cnt[j];
                }
            }
            maxLen = Math.max(maxLen, dp[i]);
        }
        int res = 0;
        for (int i = 0; i < n; i++) if (dp[i] == maxLen) res += cnt[i];
        return res;
    }

    public static void main(String[] args) {
        System.out.println(new Problem05_NumberOfLongestIncreasingSubsequence()
            .findNumberOfLIS(new int[]{1,3,5,4,7})); // 2
    }
}
