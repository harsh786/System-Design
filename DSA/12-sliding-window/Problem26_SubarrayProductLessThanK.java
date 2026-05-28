/**
 * Problem 26: Subarray Product Less Than K (LeetCode 713)
 * 
 * Approach: Sliding window with product. Shrink left when product >= k.
 * Window invariant: product of all elements in window < k.
 * Each new right adds (right-left+1) new subarrays.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like counting request combinations where combined latency
 * stays under a threshold for SLA compliance.
 */
public class Problem26_SubarrayProductLessThanK {
    public static int numSubarrayProductLessThanK(int[] nums, int k) {
        if (k <= 1) return 0;
        int left = 0, product = 1, count = 0;
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
        System.out.println(numSubarrayProductLessThanK(new int[]{1,1,1}, 2));       // 6
    }
}
