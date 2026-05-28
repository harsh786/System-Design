/**
 * Problem 39: Minimum Size Subarray Sum
 * 
 * Find minimal length subarray with sum >= target.
 * 
 * Approach: Sliding window - expand right, shrink left when sum >= target.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like finding the shortest batch of requests that
 * collectively exceed a billing threshold for alert triggering.
 */
public class Problem39_MinimumSizeSubarraySum {
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
        System.out.println(minSubArrayLen(4, new int[]{1,4,4})); // 1
        System.out.println(minSubArrayLen(11, new int[]{1,1,1,1,1,1,1,1})); // 0
    }
}
