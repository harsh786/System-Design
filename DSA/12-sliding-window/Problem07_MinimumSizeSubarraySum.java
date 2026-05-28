/**
 * Problem 7: Minimum Size Subarray Sum (LeetCode 209)
 * 
 * Approach: Variable-size sliding window. Expand right, shrink left when sum >= target.
 * Window invariant: sum of window elements. Shrink to find minimum length >= target.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like finding the minimum batch size needed to meet a throughput
 * threshold in a message processing pipeline.
 */
public class Problem07_MinimumSizeSubarraySum {
    public static int minSubArrayLen(int target, int[] nums) {
        int left = 0, sum = 0, minLen = Integer.MAX_VALUE;
        for (int right = 0; right < nums.length; right++) {
            sum += nums[right];
            while (sum >= target) {
                minLen = Math.min(minLen, right - left + 1);
                sum -= nums[left++];
            }
        }
        return minLen == Integer.MAX_VALUE ? 0 : minLen;
    }

    public static void main(String[] args) {
        System.out.println(minSubArrayLen(7, new int[]{2,3,1,2,4,3})); // 2
        System.out.println(minSubArrayLen(4, new int[]{1,4,4}));        // 1
        System.out.println(minSubArrayLen(11, new int[]{1,1,1,1,1,1,1,1})); // 0
        System.out.println(minSubArrayLen(15, new int[]{5,1,3,5,10,7,4,9,2,8})); // 2
    }
}
