import java.util.Arrays;

public class Problem38_BitmaskAssignmentDP {
    // Assign n workers to n jobs minimizing total cost
    public int minCostAssignment(int[][] cost) {
        int n = cost.length;
        int[] dp = new int[1 << n];
        Arrays.fill(dp, Integer.MAX_VALUE);
        dp[0] = 0;
        for (int mask = 0; mask < (1 << n); mask++) {
            int worker = Integer.bitCount(mask);
            if (worker >= n) continue;
            for (int job = 0; job < n; job++) {
                if ((mask & (1 << job)) != 0) continue;
                dp[mask | (1 << job)] = Math.min(dp[mask | (1 << job)], dp[mask] + cost[worker][job]);
            }
        }
        return dp[(1 << n) - 1];
    }

    public static void main(String[] args) {
        int[][] cost = {{9,2,7},{6,4,3},{5,8,1}};
        System.out.println(new Problem38_BitmaskAssignmentDP().minCostAssignment(cost)); // 7
    }
}
