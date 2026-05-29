/**
 * Problem 22: Running Sum of 1d Array (LeetCode 1480)
 * 
 * Pattern: In-place prefix sum
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Cumulative counter in Prometheus—each scrape adds to running total.
 */
import java.util.Arrays;

public class Problem22_RunningSum {

    public static int[] runningSum(int[] nums) {
        for (int i = 1; i < nums.length; i++)
            nums[i] += nums[i - 1];
        return nums;
    }

    public static void main(String[] args) {
        assert Arrays.equals(runningSum(new int[]{1, 2, 3, 4}), new int[]{1, 3, 6, 10});
        assert Arrays.equals(runningSum(new int[]{3, 1, 2, 10, 1}), new int[]{3, 4, 6, 16, 17});
        System.out.println("All tests passed!");
    }
}
