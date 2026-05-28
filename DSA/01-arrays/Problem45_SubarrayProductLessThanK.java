/**
 * Problem 45: Subarray Product Less Than K
 * Count subarrays where product of all elements < k.
 * 
 * Production Analogy: Like counting valid request batches where combined payload size
 * stays under a threshold - sliding window with multiplicative constraint.
 * 
 * O(n) time, O(1) space - sliding window
 */
public class Problem45_SubarrayProductLessThanK {

    public static int numSubarrayProductLessThanK(int[] nums, int k) {
        if (k <= 1) return 0;
        int count = 0, product = 1, left = 0;
        for (int right = 0; right < nums.length; right++) {
            product *= nums[right];
            while (product >= k) product /= nums[left++];
            count += right - left + 1;
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(numSubarrayProductLessThanK(new int[]{10,5,2,6}, 100)); // 8
        System.out.println(numSubarrayProductLessThanK(new int[]{1,2,3}, 0));       // 0
    }
}
