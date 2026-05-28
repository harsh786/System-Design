/**
 * Problem 5: Maximum Subarray (Kadane's Algorithm)
 * Find contiguous subarray with largest sum.
 * 
 * Production Analogy: Like finding the peak traffic window in a time series -
 * max sum subarray = highest sustained load period for capacity planning.
 * 
 * Brute Force: O(n^2) - check all subarrays
 * Optimal (Kadane's): O(n) time, O(1) space
 */
public class Problem05_MaximumSubarray {

    public static int maxSubArray(int[] nums) {
        int maxSum = nums[0], currentSum = nums[0];
        for (int i = 1; i < nums.length; i++) {
            currentSum = Math.max(nums[i], currentSum + nums[i]);
            maxSum = Math.max(maxSum, currentSum);
        }
        return maxSum;
    }

    public static void main(String[] args) {
        System.out.println(maxSubArray(new int[]{-2,1,-3,4,-1,2,1,-5,4})); // 6
        System.out.println(maxSubArray(new int[]{1}));                      // 1
        System.out.println(maxSubArray(new int[]{-1}));                     // -1
        System.out.println(maxSubArray(new int[]{-2,-1}));                  // -1
        System.out.println(maxSubArray(new int[]{5,4,-1,7,8}));             // 23
    }
}
