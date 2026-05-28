/**
 * Problem 47: Stone Game III
 * 
 * Take 1, 2, or 3 stones from the front. Return "Alice", "Bob", or "Tie".
 * 
 * State: dp[i] = max score difference current player can achieve from index i onward
 * Recurrence: dp[i] = max over x=1..3 of (sum(i..i+x-1) - dp[i+x])
 * 
 * Time: O(n), Space: O(n)
 */
public class Problem47_StoneGameIII {

    public static String stoneGameIII(int[] stoneValue) {
        int n = stoneValue.length;
        int[] dp = new int[n + 1];
        for (int i = n - 1; i >= 0; i--) {
            dp[i] = Integer.MIN_VALUE;
            int sum = 0;
            for (int x = 1; x <= 3 && i + x <= n; x++) {
                sum += stoneValue[i + x - 1];
                dp[i] = Math.max(dp[i], sum - dp[i + x]);
            }
        }
        if (dp[0] > 0) return "Alice";
        if (dp[0] < 0) return "Bob";
        return "Tie";
    }

    public static void main(String[] args) {
        System.out.println("=== Stone Game III ===");
        System.out.println(stoneGameIII(new int[]{1,2,3,7})); // Bob
        System.out.println(stoneGameIII(new int[]{1,2,3,-9})); // Alice
        System.out.println(stoneGameIII(new int[]{1,2,3,6})); // Tie
    }
}
