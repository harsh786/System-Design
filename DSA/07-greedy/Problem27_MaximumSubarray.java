/**
 * Problem 27: Maximum Subarray (LeetCode 53) - Kadane's Algorithm
 *
 * Greedy Choice: Extend current subarray if sum is positive; otherwise start fresh.
 *
 * Time: O(n), Space: O(1)
 *
 * Production Analogy: Finding peak sustained load period in server metrics.
 */
public class Problem27_MaximumSubarray {
    
    public static int maxSubArray(int[] nums) {
        int maxSum = nums[0], curSum = nums[0];
        for (int i = 1; i < nums.length; i++) {
            curSum = Math.max(nums[i], curSum + nums[i]);
            maxSum = Math.max(maxSum, curSum);
        }
        return maxSum;
    }
    
    public static void main(String[] args) {
        System.out.println(maxSubArray(new int[]{-2,1,-3,4,-1,2,1,-5,4})); // 6
        System.out.println(maxSubArray(new int[]{1}));                      // 1
        System.out.println(maxSubArray(new int[]{-1}));                     // -1
        System.out.println(maxSubArray(new int[]{5,4,-1,7,8}));             // 23
    }
}
