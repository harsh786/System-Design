/**
 * Problem 46: Minimum Size Subarray Sum
 * Find minimal length subarray with sum >= target.
 * 
 * Production Analogy: Like finding the minimum batch size needed to meet a throughput
 * SLA - sliding window to find shortest qualifying window.
 * 
 * O(n) time, O(1) space - sliding window
 */
public class Problem46_MinimumSizeSubarraySum {

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
    }
}
