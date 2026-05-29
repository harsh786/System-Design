/**
 * Problem 7: Minimum Size Subarray Sum (LeetCode 209)
 * 
 * Pattern: Sliding window (prefix sum variant) for minimum length subarray >= target
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Finding the shortest time window in which cumulative
 * revenue exceeds a threshold for triggering alerts.
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
        assert minSubArrayLen(7, new int[]{2, 3, 1, 2, 4, 3}) == 2;
        assert minSubArrayLen(4, new int[]{1, 4, 4}) == 1;
        assert minSubArrayLen(11, new int[]{1, 1, 1, 1, 1, 1, 1, 1}) == 0;
        assert minSubArrayLen(15, new int[]{5, 1, 3, 5, 10, 7, 4, 9, 2, 8}) == 2;
        System.out.println("All tests passed!");
    }
}
