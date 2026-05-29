import java.util.*;

public class Problem31_DeleteAndEarn {
    private Integer[] memo;

    public int deleteAndEarn(int[] nums) {
        int max = 0;
        for (int n : nums) max = Math.max(max, n);
        int[] sum = new int[max + 1];
        for (int n : nums) sum[n] += n;
        memo = new Integer[max + 1];
        return helper(sum, max);
    }

    private int helper(int[] sum, int i) {
        if (i <= 0) return 0;
        if (memo[i] != null) return memo[i];
        memo[i] = Math.max(sum[i] + helper(sum, i - 2), helper(sum, i - 1));
        return memo[i];
    }

    public static void main(String[] args) {
        Problem31_DeleteAndEarn sol = new Problem31_DeleteAndEarn();
        System.out.println(sol.deleteAndEarn(new int[]{3,4,2})); // 6
    }
}
