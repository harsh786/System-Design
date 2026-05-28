import java.util.*;
/**
 * Problem 29: Longest Harmonious Subsequence (LeetCode 594)
 * 
 * Approach: Sort + sliding window. Window must have max-min == 1.
 * Window invariant: difference between max and min in window <= 1.
 * Only count when difference is exactly 1.
 * 
 * Time: O(n log n), Space: O(1)
 * 
 * Production Analogy: Like finding the longest period where version differences
 * between deployed services is exactly 1 (rolling update window).
 */
public class Problem29_LongestHarmoniousSubsequence {
    public static int findLHS(int[] nums) {
        Arrays.sort(nums);
        int left = 0, maxLen = 0;
        for (int right = 0; right < nums.length; right++) {
            while (nums[right] - nums[left] > 1) left++;
            if (nums[right] - nums[left] == 1) {
                maxLen = Math.max(maxLen, right - left + 1);
            }
        }
        return maxLen;
    }

    public static void main(String[] args) {
        System.out.println(findLHS(new int[]{1,3,2,2,5,2,3,7})); // 5
        System.out.println(findLHS(new int[]{1,2,3,4}));           // 2
        System.out.println(findLHS(new int[]{1,1,1,1}));           // 0
    }
}
