import java.util.*;

public class Problem15_BurstBalloons {
    private Integer[][] memo;

    public int maxCoins(int[] nums) {
        int n = nums.length + 2;
        int[] arr = new int[n];
        arr[0] = arr[n - 1] = 1;
        for (int i = 0; i < nums.length; i++) arr[i + 1] = nums[i];
        memo = new Integer[n][n];
        return helper(arr, 0, n - 1);
    }

    private int helper(int[] arr, int left, int right) {
        if (left + 1 == right) return 0;
        if (memo[left][right] != null) return memo[left][right];
        int max = 0;
        for (int i = left + 1; i < right; i++) {
            max = Math.max(max, arr[left] * arr[i] * arr[right] + helper(arr, left, i) + helper(arr, i, right));
        }
        memo[left][right] = max;
        return max;
    }

    public static void main(String[] args) {
        Problem15_BurstBalloons sol = new Problem15_BurstBalloons();
        System.out.println("Burst Balloons [3,1,5,8]: " + sol.maxCoins(new int[]{3,1,5,8})); // 167
    }
}
