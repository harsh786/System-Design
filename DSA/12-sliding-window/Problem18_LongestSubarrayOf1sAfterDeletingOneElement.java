/**
 * Problem 18: Longest Subarray of 1's After Deleting One Element (LeetCode 1493)
 * 
 * Approach: Sliding window with at most 1 zero allowed (must delete one element).
 * Window invariant: at most 1 zero in window. Result is windowSize - 1.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like finding longest healthy streak allowing one failure
 * to be removed from uptime calculations.
 */
public class Problem18_LongestSubarrayOf1sAfterDeletingOneElement {
    public static int longestSubarray(int[] nums) {
        int left = 0, zeros = 0, maxLen = 0;
        for (int right = 0; right < nums.length; right++) {
            if (nums[right] == 0) zeros++;
            while (zeros > 1) {
                if (nums[left] == 0) zeros--;
                left++;
            }
            maxLen = Math.max(maxLen, right - left); // -1 because must delete one
        }
        return maxLen;
    }

    public static void main(String[] args) {
        System.out.println(longestSubarray(new int[]{1,1,0,1}));     // 3
        System.out.println(longestSubarray(new int[]{0,1,1,1,0,1,1,0,1})); // 5
        System.out.println(longestSubarray(new int[]{1,1,1}));       // 2
        System.out.println(longestSubarray(new int[]{0,0,0}));       // 0
    }
}
