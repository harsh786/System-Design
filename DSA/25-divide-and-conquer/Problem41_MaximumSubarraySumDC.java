/**
 * Problem 41: Maximum Subarray Sum with D&C (variant with tracking indices)
 * 
 * D&C Approach (same as Problem 6 but returns the actual subarray):
 * - DIVIDE: Split at midpoint
 * - CONQUER: Find max subarray in left, right, and crossing
 * - COMBINE: Return the one with maximum sum along with indices
 * 
 * Time: O(n log n), Space: O(log n)
 * 
 * Production Analogy:
 * - Identifying peak traffic periods (start/end timestamps)
 * - Finding most profitable trading window across distributed time partitions
 * - Resource utilization peak detection in monitoring systems
 */
public class Problem41_MaximumSubarraySumDC {

    // Returns [sum, startIndex, endIndex]
    public static int[] maxSubArray(int[] nums) {
        return helper(nums, 0, nums.length - 1);
    }

    private static int[] helper(int[] nums, int lo, int hi) {
        if (lo == hi) return new int[]{nums[lo], lo, lo};
        
        int mid = lo + (hi - lo) / 2;
        int[] left = helper(nums, lo, mid);
        int[] right = helper(nums, mid + 1, hi);
        int[] cross = maxCrossing(nums, lo, mid, hi);
        
        if (left[0] >= right[0] && left[0] >= cross[0]) return left;
        if (right[0] >= left[0] && right[0] >= cross[0]) return right;
        return cross;
    }

    private static int[] maxCrossing(int[] nums, int lo, int mid, int hi) {
        int leftSum = Integer.MIN_VALUE, sum = 0, leftIdx = mid;
        for (int i = mid; i >= lo; i--) {
            sum += nums[i];
            if (sum > leftSum) { leftSum = sum; leftIdx = i; }
        }
        int rightSum = Integer.MIN_VALUE;
        sum = 0;
        int rightIdx = mid + 1;
        for (int i = mid + 1; i <= hi; i++) {
            sum += nums[i];
            if (sum > rightSum) { rightSum = sum; rightIdx = i; }
        }
        return new int[]{leftSum + rightSum, leftIdx, rightIdx};
    }

    public static void main(String[] args) {
        int[] r1 = maxSubArray(new int[]{-2,1,-3,4,-1,2,1,-5,4});
        System.out.printf("Sum=%d, range=[%d,%d]%n", r1[0], r1[1], r1[2]); // Sum=6, range=[3,6]
        
        int[] r2 = maxSubArray(new int[]{1});
        System.out.printf("Sum=%d, range=[%d,%d]%n", r2[0], r2[1], r2[2]); // Sum=1, range=[0,0]
        
        int[] r3 = maxSubArray(new int[]{-1,-2,-3});
        System.out.printf("Sum=%d, range=[%d,%d]%n", r3[0], r3[1], r3[2]); // Sum=-1, range=[0,0]
        
        int[] r4 = maxSubArray(new int[]{5,4,-1,7,8});
        System.out.printf("Sum=%d, range=[%d,%d]%n", r4[0], r4[1], r4[2]); // Sum=23, range=[0,4]
    }
}
