import java.util.*;

public class Problem06_StoneGameIII {
    // 1406. Stone Game III: Take 1,2, or 3 stones from the front. Return "Alice", "Bob", or "Tie".
    
    public String stoneGameIII(int[] stoneValue) {
        int n = stoneValue.length;
        int[] dp = new int[n + 1]; // dp[i] = max score diff for current player from index i
        for (int i = n - 1; i >= 0; i--) {
            dp[i] = Integer.MIN_VALUE;
            int sum = 0;
            for (int k = 1; k <= 3 && i + k <= n; k++) {
                sum += stoneValue[i + k - 1];
                dp[i] = Math.max(dp[i], sum - dp[i + k]);
            }
        }
        if (dp[0] > 0) return "Alice";
        if (dp[0] < 0) return "Bob";
        return "Tie";
    }
    
    public static void main(String[] args) {
        Problem06_StoneGameIII sol = new Problem06_StoneGameIII();
        System.out.println(sol.stoneGameIII(new int[]{1,2,3,7}));    // "Bob"
        System.out.println(sol.stoneGameIII(new int[]{1,2,3,-9}));   // "Alice"
        System.out.println(sol.stoneGameIII(new int[]{1,2,3,6}));    // "Tie"
    }
}
