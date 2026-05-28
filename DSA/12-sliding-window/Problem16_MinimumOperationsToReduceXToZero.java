/**
 * Problem 16: Minimum Operations to Reduce X to Zero (LeetCode 1658)
 * 
 * Approach: Equivalent to finding longest subarray with sum = totalSum - x.
 * Window invariant: sum of window == target (totalSum - x).
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like finding the largest contiguous block of data to KEEP
 * when trimming from both ends to meet a storage quota.
 */
public class Problem16_MinimumOperationsToReduceXToZero {
    public static int minOperations(int[] nums, int x) {
        int totalSum = 0;
        for (int n : nums) totalSum += n;
        int target = totalSum - x;
        if (target < 0) return -1;
        if (target == 0) return nums.length;
        int left = 0, sum = 0, maxLen = -1;
        for (int right = 0; right < nums.length; right++) {
            sum += nums[right];
            while (sum > target) {
                sum -= nums[left++];
            }
            if (sum == target) maxLen = Math.max(maxLen, right - left + 1);
        }
        return maxLen == -1 ? -1 : nums.length - maxLen;
    }

    public static void main(String[] args) {
        System.out.println(minOperations(new int[]{1,1,4,2,3}, 5));     // 2
        System.out.println(minOperations(new int[]{5,6,7,8,9}, 4));     // -1
        System.out.println(minOperations(new int[]{3,2,20,1,1,3}, 10)); // 5
    }
}
