import java.util.*;

public class Problem26_PaintHouse {
    private Integer[][] memo;

    public int minCost(int[][] costs) {
        if (costs.length == 0) return 0;
        memo = new Integer[costs.length][3];
        return Math.min(helper(costs, 0, 0), Math.min(helper(costs, 0, 1), helper(costs, 0, 2)));
    }

    private int helper(int[][] costs, int i, int color) {
        if (i == costs.length) return 0;
        if (memo[i][color] != null) return memo[i][color];
        int min = Integer.MAX_VALUE;
        for (int c = 0; c < 3; c++) {
            if (c != color || i == 0) min = Math.min(min, costs[i][c] + helper(costs, i + 1, c));
        }
        memo[i][color] = costs[i][color] + Math.min(helper(costs, i+1, (color+1)%3), helper(costs, i+1, (color+2)%3));
        return memo[i][color];
    }

    public static void main(String[] args) {
        Problem26_PaintHouse sol = new Problem26_PaintHouse();
        System.out.println(sol.minCost(new int[][]{{17,2,17},{16,16,5},{14,3,19}})); // 10
    }
}
