/**
 * Problem 47: Longest Subarray with Sum at Most K
 * 
 * Pattern: Sliding window (for non-negative) or prefix sum + binary search (general)
 * Here we implement sliding window for non-negative arrays.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Finding the longest time window where cumulative bandwidth
 * usage stays within a quota for fair-use policy enforcement.
 */
public class Problem47_LongestSubarraySumAtMostK {

    // For non-negative elements
    public static int longestSubarray(int[] nums, int k) {
        int left = 0, sum = 0, maxLen = 0;
        for (int right = 0; right < nums.length; right++) {
            sum += nums[right];
            while (sum > k && left <= right) {
                sum -= nums[left++];
            }
            maxLen = Math.max(maxLen, right - left + 1);
        }
        return maxLen;
    }

    public static void main(String[] args) {
        assert longestSubarray(new int[]{1, 2, 3, 4, 5}, 9) == 3;  // [2,3,4]
        assert longestSubarray(new int[]{1, 1, 1, 1, 1}, 3) == 3;
        assert longestSubarray(new int[]{5, 1, 1, 1}, 4) == 3;
        assert longestSubarray(new int[]{10}, 5) == 0;
        assert longestSubarray(new int[]{1, 2, 3}, 100) == 3;
        System.out.println("All tests passed!");
    }
}
