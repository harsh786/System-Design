import java.util.*;

public class Problem41_MinimumCostToCutAStick {
    private Integer[][] memo;

    public int minCost(int n, int[] cuts) {
        Arrays.sort(cuts);
        int[] newCuts = new int[cuts.length + 2];
        newCuts[0] = 0;
        newCuts[newCuts.length - 1] = n;
        System.arraycopy(cuts, 0, newCuts, 1, cuts.length);
        memo = new Integer[newCuts.length][newCuts.length];
        return helper(newCuts, 0, newCuts.length - 1);
    }

    private int helper(int[] cuts, int l, int r) {
        if (r - l <= 1) return 0;
        if (memo[l][r] != null) return memo[l][r];
        int min = Integer.MAX_VALUE;
        for (int i = l + 1; i < r; i++) {
            min = Math.min(min, cuts[r] - cuts[l] + helper(cuts, l, i) + helper(cuts, i, r));
        }
        memo[l][r] = min;
        return min;
    }

    public static void main(String[] args) {
        Problem41_MinimumCostToCutAStick sol = new Problem41_MinimumCostToCutAStick();
        System.out.println(sol.minCost(7, new int[]{1,3,4,5})); // 16
    }
}
