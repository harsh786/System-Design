import java.util.*;

public class Problem41_StoneGameVIII {
    // 1872. Stone Game VIII: n stones. Take leftmost x>=2 stones, replace with their sum.
    // Score = prefix sum. Maximize Alice - Bob.
    
    public int stoneGameVIII(int[] stones) {
        int n = stones.length;
        int[] prefix = new int[n];
        prefix[0] = stones[0];
        for (int i = 1; i < n; i++) prefix[i] = prefix[i-1] + stones[i];
        // dp[i] = max score diff when current player considers taking first i+1 stones
        // Work from right to left: dp[i] = max(prefix[i] - dp[i+1], dp[i+1])
        int dp = prefix[n-1]; // taking all
        for (int i = n - 2; i >= 1; i--) {
            dp = Math.max(prefix[i] - dp, dp);
        }
        return dp;
    }
    
    public static void main(String[] args) {
        Problem41_StoneGameVIII sol = new Problem41_StoneGameVIII();
        System.out.println(sol.stoneGameVIII(new int[]{-1,2,-3,4,-5})); // 5
        System.out.println(sol.stoneGameVIII(new int[]{7,-6,5,10,5,-2,-6})); // 13
    }
}
