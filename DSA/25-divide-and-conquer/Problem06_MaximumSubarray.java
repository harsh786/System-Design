/**
 * Problem 6: Maximum Subarray (D&C approach) - LeetCode 53
 * 
 * D&C Approach:
 * - DIVIDE: Split array at midpoint
 * - CONQUER: Find max subarray in left half and right half
 * - COMBINE: Find max subarray crossing the midpoint, return max of all three
 * 
 * Recurrence: T(n) = 2T(n/2) + O(n)
 * Time: O(n log n), Space: O(log n) recursion stack
 * 
 * Production Analogy:
 * - Parallel profit/loss computation across time-partitioned financial data
 * - Finding peak usage periods across distributed log partitions
 */
public class Problem06_MaximumSubarray {

    public static int maxSubArray(int[] nums) {
        return helper(nums, 0, nums.length - 1);
    }

    private static int helper(int[] nums, int left, int right) {
        if (left == right) return nums[left];
        
        int mid = left + (right - left) / 2;
        int leftMax = helper(nums, left, mid);
        int rightMax = helper(nums, mid + 1, right);
        int crossMax = maxCrossing(nums, left, mid, right);
        
        return Math.max(Math.max(leftMax, rightMax), crossMax);
    }

    private static int maxCrossing(int[] nums, int left, int mid, int right) {
        int leftSum = Integer.MIN_VALUE, sum = 0;
        for (int i = mid; i >= left; i--) {
            sum += nums[i];
            leftSum = Math.max(leftSum, sum);
        }
        int rightSum = Integer.MIN_VALUE;
        sum = 0;
        for (int i = mid + 1; i <= right; i++) {
            sum += nums[i];
            rightSum = Math.max(rightSum, sum);
        }
        return leftSum + rightSum;
    }

    public static void main(String[] args) {
        System.out.println(maxSubArray(new int[]{-2,1,-3,4,-1,2,1,-5,4})); // 6
        System.out.println(maxSubArray(new int[]{1})); // 1
        System.out.println(maxSubArray(new int[]{5,4,-1,7,8})); // 23
        System.out.println(maxSubArray(new int[]{-1,-2,-3})); // -1
        System.out.println(maxSubArray(new int[]{-2,1})); // 1
    }
}
