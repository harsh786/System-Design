/**
 * Problem 23: Maximum Average Subarray I (LeetCode 643)
 * 
 * Pattern: Fixed-size sliding window (prefix sum variant)
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Computing rolling average latency over a fixed time window for SLA dashboards.
 */
public class Problem23_MaxAverageSubarrayI {

    public static double findMaxAverage(int[] nums, int k) {
        int sum = 0;
        for (int i = 0; i < k; i++) sum += nums[i];
        int maxSum = sum;
        for (int i = k; i < nums.length; i++) {
            sum += nums[i] - nums[i - k];
            maxSum = Math.max(maxSum, sum);
        }
        return (double) maxSum / k;
    }

    public static void main(String[] args) {
        assert Math.abs(findMaxAverage(new int[]{1, 12, -5, -6, 50, 3}, 4) - 12.75) < 0.001;
        assert Math.abs(findMaxAverage(new int[]{5}, 1) - 5.0) < 0.001;
        System.out.println("All tests passed!");
    }
}
