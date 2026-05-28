/**
 * Problem 38: Subarray Product Less Than K
 * 
 * Count subarrays where product of all elements is less than k.
 * 
 * Approach: Sliding window with two pointers. Shrink left when product >= k.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like finding all time windows where combined error rates
 * of consecutive services stay below an SLA threshold.
 */
public class Problem38_SubarrayProductLessThanK {
    public static int numSubarrayProductLessThanK(int[] nums, int k) {
        if (k <= 1) return 0;
        int product = 1, count = 0, left = 0;
        for (int right = 0; right < nums.length; right++) {
            product *= nums[right];
            while (product >= k) product /= nums[left++];
            count += right - left + 1;
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(numSubarrayProductLessThanK(new int[]{10,5,2,6}, 100)); // 8
        System.out.println(numSubarrayProductLessThanK(new int[]{1,2,3}, 0)); // 0
    }
}
