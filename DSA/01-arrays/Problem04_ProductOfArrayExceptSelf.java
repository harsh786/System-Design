import java.util.*;

/**
 * Problem 4: Product of Array Except Self
 * Return array where each element is product of all others, without division.
 * 
 * Production Analogy: Like computing aggregate metrics excluding self - 
 * e.g., average response time of all services except the current one for anomaly detection.
 * 
 * Optimal: O(n) time, O(1) extra space (output doesn't count)
 * Use prefix and suffix products.
 */
public class Problem04_ProductOfArrayExceptSelf {

    public static int[] productExceptSelf(int[] nums) {
        int n = nums.length;
        int[] result = new int[n];
        result[0] = 1;
        for (int i = 1; i < n; i++) result[i] = result[i-1] * nums[i-1];
        int suffix = 1;
        for (int i = n - 1; i >= 0; i--) {
            result[i] *= suffix;
            suffix *= nums[i];
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(productExceptSelf(new int[]{1,2,3,4})));  // [24,12,8,6]
        System.out.println(Arrays.toString(productExceptSelf(new int[]{-1,1,0,-3,3}))); // [0,0,9,0,0]
        System.out.println(Arrays.toString(productExceptSelf(new int[]{0,0})));      // [0,0]
    }
}
