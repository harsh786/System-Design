/**
 * Problem 14: Maximum Sum Circular Subarray (LeetCode 918)
 * 
 * Pattern: Answer is max(maxSubarray, totalSum - minSubarray) using Kadane's
 * The circular case wraps around = total - minimum subarray in the middle.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Finding peak load period in a circular schedule (24h clock)
 * where peak may wrap past midnight.
 */
public class Problem14_MaxSumCircularSubarray {

    public static int maxSubarraySumCircular(int[] nums) {
        int totalSum = 0, maxSum = Integer.MIN_VALUE, curMax = 0;
        int minSum = Integer.MAX_VALUE, curMin = 0;
        for (int num : nums) {
            curMax = Math.max(curMax + num, num);
            maxSum = Math.max(maxSum, curMax);
            curMin = Math.min(curMin + num, num);
            minSum = Math.min(minSum, curMin);
            totalSum += num;
        }
        // If all negative, maxSum is the answer (can't take empty subarray)
        return maxSum < 0 ? maxSum : Math.max(maxSum, totalSum - minSum);
    }

    public static void main(String[] args) {
        assert maxSubarraySumCircular(new int[]{1, -2, 3, -2}) == 3;
        assert maxSubarraySumCircular(new int[]{5, -3, 5}) == 10;
        assert maxSubarraySumCircular(new int[]{-3, -2, -3}) == -2;
        assert maxSubarraySumCircular(new int[]{3, -1, 2, -1}) == 4;
        System.out.println("All tests passed!");
    }
}
