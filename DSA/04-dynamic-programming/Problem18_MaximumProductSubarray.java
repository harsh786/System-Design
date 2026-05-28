/**
 * Problem 18: Maximum Product Subarray
 * 
 * Track both max and min products (negative * negative = positive).
 * 
 * State: maxProd[i], minProd[i] = max/min product ending at i
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like tracking cumulative effect of multipliers in a pipeline
 * where negative factors can flip sign.
 */
public class Problem18_MaximumProductSubarray {

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
        System.out.println("=== Maximum Product Subarray ===");
        System.out.println(maxProduct(new int[]{2,3,-2,4})); // 6
        System.out.println(maxProduct(new int[]{-2,0,-1})); // 0
        System.out.println(maxProduct(new int[]{-2,3,-4})); // 24
    }
}
