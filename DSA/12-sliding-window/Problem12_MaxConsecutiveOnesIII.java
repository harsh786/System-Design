/**
 * Problem 12: Max Consecutive Ones III (LeetCode 1004)
 * 
 * Approach: Sliding window allowing at most k zeros in window.
 * Window invariant: number of zeros in window <= k.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like finding the longest uptime streak allowing k maintenance
 * windows (downtime events) to be "forgiven."
 */
public class Problem12_MaxConsecutiveOnesIII {
    public static int longestOnes(int[] nums, int k) {
        int left = 0, zeros = 0, maxLen = 0;
        for (int right = 0; right < nums.length; right++) {
            if (nums[right] == 0) zeros++;
            while (zeros > k) {
                if (nums[left] == 0) zeros--;
                left++;
            }
            maxLen = Math.max(maxLen, right - left + 1);
        }
        return maxLen;
    }

    public static void main(String[] args) {
        System.out.println(longestOnes(new int[]{1,1,1,0,0,0,1,1,1,1,0}, 2)); // 6
        System.out.println(longestOnes(new int[]{0,0,1,1,0,0,1,1,1,0,1,1,0,0,0,1,1,1,1}, 3)); // 10
        System.out.println(longestOnes(new int[]{1,1,1,1}, 0)); // 4
        System.out.println(longestOnes(new int[]{0,0,0,0}, 0)); // 0
    }
}
