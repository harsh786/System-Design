/**
 * Problem 36: Longest Nice Subarray (LeetCode 2401)
 * 
 * Approach: Sliding window where AND of any two elements == 0.
 * Track OR of all window elements. New element is valid if (OR & nums[right]) == 0.
 * Window invariant: bitwise AND of any pair == 0 (no shared set bits).
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like finding the longest set of non-overlapping feature flags
 * that can be combined in a bitmask.
 */
public class Problem36_LongestNiceSubarray {
    public static int longestNiceSubarray(int[] nums) {
        int left = 0, orVal = 0, maxLen = 0;
        for (int right = 0; right < nums.length; right++) {
            while ((orVal & nums[right]) != 0) {
                orVal ^= nums[left++];
            }
            orVal |= nums[right];
            maxLen = Math.max(maxLen, right - left + 1);
        }
        return maxLen;
    }

    public static void main(String[] args) {
        System.out.println(longestNiceSubarray(new int[]{1,3,8,48,10})); // 3
        System.out.println(longestNiceSubarray(new int[]{3,1,5,11,13})); // 1
    }
}
