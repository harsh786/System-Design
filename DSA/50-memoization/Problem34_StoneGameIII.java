import java.util.*;

public class Problem34_StoneGameIII {
    private Integer[] memo;

    public String stoneGameIII(int[] stoneValue) {
        memo = new Integer[stoneValue.length];
        int[] suffix = new int[stoneValue.length + 1];
        for (int i = stoneValue.length - 1; i >= 0; i--) suffix[i] = suffix[i+1] + stoneValue[i];
        int aliceScore = helper(stoneValue, suffix, 0);
        int bobScore = suffix[0] - aliceScore;
        if (aliceScore > bobScore) return "Alice";
        if (aliceScore < bobScore) return "Bob";
        return "Tie";
    }

    private int helper(int[] sv, int[] suffix, int i) {
        if (i >= sv.length) return 0;
        if (memo[i] != null) return memo[i];
        int max = Integer.MIN_VALUE;
        for (int x = 1; x <= 3 && i + x <= sv.length; x++) {
            max = Math.max(max, suffix[i] - helper(sv, suffix, i + x));
        }
        memo[i] = max;
        return max;
    }

    public static void main(String[] args) {
        Problem34_StoneGameIII sol = new Problem34_StoneGameIII();
        System.out.println(sol.stoneGameIII(new int[]{1,2,3,7})); // "Bob"
    }
}
