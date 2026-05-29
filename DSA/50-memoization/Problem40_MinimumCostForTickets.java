import java.util.*;

public class Problem40_MinimumCostForTickets {
    private Integer[] memo;
    private Set<Integer> travelDays;

    public int mincostTickets(int[] days, int[] costs) {
        memo = new Integer[366];
        travelDays = new HashSet<>();
        for (int d : days) travelDays.add(d);
        return helper(days[0], days[days.length - 1], costs);
    }

    private int helper(int day, int lastDay, int[] costs) {
        if (day > lastDay) return 0;
        if (memo[day] != null) return memo[day];
        if (!travelDays.contains(day)) return memo[day] = helper(day + 1, lastDay, costs);
        memo[day] = Math.min(costs[0] + helper(day + 1, lastDay, costs),
                   Math.min(costs[1] + helper(day + 7, lastDay, costs),
                            costs[2] + helper(day + 30, lastDay, costs)));
        return memo[day];
    }

    public static void main(String[] args) {
        Problem40_MinimumCostForTickets sol = new Problem40_MinimumCostForTickets();
        System.out.println(sol.mincostTickets(new int[]{1,4,6,7,8,20}, new int[]{2,7,15})); // 11
    }
}
