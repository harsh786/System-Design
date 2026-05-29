/**
 * Problem 46: Maximum Subarray Sum After One Operation
 * 
 * Pattern: DP with prefix-sum thinking. Track max subarray sum where we either
 * have or haven't used the one squaring operation.
 * 
 * States: noOp[i] = max subarray ending at i without squaring
 *         withOp[i] = max subarray ending at i having squared exactly one element
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Finding peak revenue window if you could apply one promotional
 * boost (squaring effect) to any single day's revenue.
 */
public class Problem46_MaxSubarraySumAfterOneOp {

    public static long maxSumAfterOneSquare(int[] nums) {
        long noOp = nums[0], withOp = (long) nums[0] * nums[0];
        long maxSum = withOp;
        for (int i = 1; i < nums.length; i++) {
            long sq = (long) nums[i] * nums[i];
            withOp = Math.max(sq, Math.max(noOp + sq, withOp + nums[i]));
            noOp = Math.max(nums[i], noOp + nums[i]);
            maxSum = Math.max(maxSum, withOp);
        }
        return maxSum;
    }

    public static void main(String[] args) {
        assert maxSumAfterOneSquare(new int[]{2, -1, -4, -3}) == 17; // square -4 -> 16, subarray [-1,16]? actually [2,-1,16]=17
        assert maxSumAfterOneSquare(new int[]{1, -1, 1, 1, -1, -1, 1}) == 4;
        assert maxSumAfterOneSquare(new int[]{-3, -2, -1}) == 9; // square -3
        System.out.println("All tests passed!");
    }
}
