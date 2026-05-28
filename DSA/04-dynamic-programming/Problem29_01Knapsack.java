/**
 * Problem 29: 0/1 Knapsack
 * 
 * Given weights and values of n items, find max value in knapsack of capacity W.
 * Each item can be used at most once.
 * 
 * State: dp[j] = max value with capacity j
 * Recurrence: dp[j] = max(dp[j], dp[j - weight[i]] + value[i]) (iterate j backwards)
 * 
 * Time: O(n*W), Space: O(W)
 * 
 * Production Analogy: Like selecting features/services to deploy given limited
 * compute/memory budget, each with different resource cost and business value.
 */
public class Problem29_01Knapsack {

    public static int knapsack(int[] weights, int[] values, int W) {
        int[] dp = new int[W + 1];
        for (int i = 0; i < weights.length; i++) {
            for (int j = W; j >= weights[i]; j--) {
                dp[j] = Math.max(dp[j], dp[j - weights[i]] + values[i]);
            }
        }
        return dp[W];
    }

    public static void main(String[] args) {
        System.out.println("=== 0/1 Knapsack ===");
        System.out.println(knapsack(new int[]{1,3,4,5}, new int[]{1,4,5,7}, 7)); // 9
        System.out.println(knapsack(new int[]{2,3,4,5}, new int[]{3,4,5,6}, 5)); // 7
    }
}
