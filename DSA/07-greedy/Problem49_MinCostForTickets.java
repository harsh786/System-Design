/**
 * Problem 49: Minimum Cost For Tickets (LeetCode 983)
 *
 * DP with greedy ticket selection: For each travel day, pick cheapest ticket option.
 *
 * Time: O(365), Space: O(365)
 *
 * Production Analogy: Choosing optimal subscription plans (daily/weekly/monthly) for usage pattern.
 */
import java.util.*;
public class Problem49_MinCostForTickets {
    
    public static int mincostTickets(int[] days, int[] costs) {
        Set<Integer> travelDays = new HashSet<>();
        for (int d : days) travelDays.add(d);
        int lastDay = days[days.length - 1];
        int[] dp = new int[lastDay + 1];
        for (int i = 1; i <= lastDay; i++) {
            if (!travelDays.contains(i)) { dp[i] = dp[i-1]; continue; }
            dp[i] = dp[i-1] + costs[0];
            dp[i] = Math.min(dp[i], dp[Math.max(0, i-7)] + costs[1]);
            dp[i] = Math.min(dp[i], dp[Math.max(0, i-30)] + costs[2]);
        }
        return dp[lastDay];
    }
    
    public static void main(String[] args) {
        System.out.println(mincostTickets(new int[]{1,4,6,7,8,20}, new int[]{2,7,15}));          // 11
        System.out.println(mincostTickets(new int[]{1,2,3,4,5,6,7,8,9,10,30,31}, new int[]{2,7,15})); // 17
    }
}
