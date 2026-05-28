/**
 * Problem 32: Min Cost Climbing Stairs
 * 
 * Pay cost[i] to step on stair i. Can climb 1 or 2 steps. Start from 0 or 1.
 * 
 * State: dp[i] = min cost to reach step i
 * Time: O(n), Space: O(1)
 */
public class Problem32_MinCostClimbingStairs {

    public static int minCostClimbingStairs(int[] cost) {
        int prev2 = 0, prev1 = 0;
        for (int i = 2; i <= cost.length; i++) {
            int curr = Math.min(prev1 + cost[i - 1], prev2 + cost[i - 2]);
            prev2 = prev1;
            prev1 = curr;
        }
        return prev1;
    }

    public static void main(String[] args) {
        System.out.println("=== Min Cost Climbing Stairs ===");
        System.out.println(minCostClimbingStairs(new int[]{10,15,20})); // 15
        System.out.println(minCostClimbingStairs(new int[]{1,100,1,1,1,100,1,1,100,1})); // 6
    }
}
