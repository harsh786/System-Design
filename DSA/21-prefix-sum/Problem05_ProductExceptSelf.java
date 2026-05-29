/**
 * Problem 5: Product of Array Except Self (LeetCode 238)
 * 
 * Pattern: Prefix product + suffix product (no division)
 * 
 * result[i] = product of all elements to left * product of all elements to right
 * 
 * Time: O(n), Space: O(1) extra (output array doesn't count)
 * 
 * Production Analogy: Computing normalized weights in a load balancer where each
 * server's share is total_capacity / its_capacity (without division for numerical stability).
 */
import java.util.Arrays;

public class Problem05_ProductExceptSelf {

    public static int[] productExceptSelf(int[] nums) {
        int n = nums.length;
        int[] result = new int[n];
        result[0] = 1;
        // Left prefix products
        for (int i = 1; i < n; i++)
            result[i] = result[i - 1] * nums[i - 1];
        // Right suffix products multiplied in
        int right = 1;
        for (int i = n - 1; i >= 0; i--) {
            result[i] *= right;
            right *= nums[i];
        }
        return result;
    }

    public static void main(String[] args) {
        assert Arrays.equals(productExceptSelf(new int[]{1, 2, 3, 4}), new int[]{24, 12, 8, 6});
        assert Arrays.equals(productExceptSelf(new int[]{-1, 1, 0, -3, 3}), new int[]{0, 0, 9, 0, 0});
        assert Arrays.equals(productExceptSelf(new int[]{2, 2}), new int[]{2, 2});
        System.out.println("All tests passed!");
    }
}
