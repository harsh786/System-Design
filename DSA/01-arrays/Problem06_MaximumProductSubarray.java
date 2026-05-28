/**
 * Problem 6: Maximum Product Subarray
 * Find contiguous subarray with largest product.
 * 
 * Production Analogy: Like computing compound growth rates - need to track both
 * max and min because a negative * negative = positive (debt cancellation analogy).
 * 
 * O(n) time, O(1) space - track both max and min products at each position.
 */
public class Problem06_MaximumProductSubarray {

    public static int maxProduct(int[] nums) {
        int maxProd = nums[0], minProd = nums[0], result = nums[0];
        for (int i = 1; i < nums.length; i++) {
            if (nums[i] < 0) { int tmp = maxProd; maxProd = minProd; minProd = tmp; }
            maxProd = Math.max(nums[i], maxProd * nums[i]);
            minProd = Math.min(nums[i], minProd * nums[i]);
            result = Math.max(result, maxProd);
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(maxProduct(new int[]{2,3,-2,4}));   // 6
        System.out.println(maxProduct(new int[]{-2,0,-1}));    // 0
        System.out.println(maxProduct(new int[]{-2,3,-4}));    // 24
        System.out.println(maxProduct(new int[]{-2}));          // -2
        System.out.println(maxProduct(new int[]{0,2}));         // 2
    }
}
