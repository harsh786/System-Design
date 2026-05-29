import java.util.*;

public class Problem22_StoneGameVII {
    // 1690. Stone Game VII: Remove a stone from either end. Score = sum of remaining.
    // Maximize score difference.
    
    public int stoneGameVII(int[] stones) {
        int n = stones.length;
        int[] prefix = new int[n + 1];
        for (int i = 0; i < n; i++) prefix[i+1] = prefix[i] + stones[i];
        int[][] dp = new int[n][n];
        for (int len = 2; len <= n; len++) {
            for (int i = 0; i <= n - len; i++) {
                int j = i + len - 1;
                int sum = prefix[j+1] - prefix[i];
                // remove left: opponent gets dp[i+1][j], current scores sum - stones[i]
                // remove right: opponent gets dp[i][j-1], current scores sum - stones[j]
                dp[i][j] = Math.max(
                    (sum - stones[i]) - dp[i+1][j],
                    (sum - stones[j]) - dp[i][j-1]
                );
            }
        }
        return dp[0][n-1];
    }
    
    public static void main(String[] args) {
        Problem22_StoneGameVII sol = new Problem22_StoneGameVII();
        System.out.println(sol.stoneGameVII(new int[]{5,3,1,4,2})); // 6
    }
}
