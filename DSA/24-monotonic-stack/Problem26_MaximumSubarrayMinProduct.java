import java.util.*;

/**
 * Problem 26: Maximum Subarray Min-Product (LeetCode 1856)
 * 
 * Min-product = min(subarray) * sum(subarray). Find maximum min-product.
 * 
 * Approach: For each element as the minimum, find its extent using monotonic stack
 * (previous and next smaller). Use prefix sums for range sum.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Finding the time window where minimum throughput * total
 * data processed is maximized (balanced load analysis).
 */
public class Problem26_MaximumSubarrayMinProduct {
    
    public int maxSumMinProduct(int[] nums) {
        int n = nums.length;
        long MOD = 1_000_000_007;
        long[] prefix = new long[n + 1];
        for (int i = 0; i < n; i++) prefix[i + 1] = prefix[i] + nums[i];
        
        int[] left = new int[n], right = new int[n];
        Deque<Integer> stack = new ArrayDeque<>();
        
        for (int i = 0; i < n; i++) {
            while (!stack.isEmpty() && nums[stack.peek()] >= nums[i]) stack.pop();
            left[i] = stack.isEmpty() ? -1 : stack.peek();
            stack.push(i);
        }
        stack.clear();
        for (int i = n - 1; i >= 0; i--) {
            while (!stack.isEmpty() && nums[stack.peek()] >= nums[i]) stack.pop();
            right[i] = stack.isEmpty() ? n : stack.peek();
            stack.push(i);
        }
        
        long maxProduct = 0;
        for (int i = 0; i < n; i++) {
            long sum = prefix[right[i]] - prefix[left[i] + 1];
            maxProduct = Math.max(maxProduct, (long) nums[i] * sum);
        }
        return (int)(maxProduct % MOD);
    }
    
    public static void main(String[] args) {
        Problem26_MaximumSubarrayMinProduct sol = new Problem26_MaximumSubarrayMinProduct();
        System.out.println(sol.maxSumMinProduct(new int[]{1,2,3,2})); // 14
        System.out.println(sol.maxSumMinProduct(new int[]{2,3,3,1,2})); // 18
        System.out.println(sol.maxSumMinProduct(new int[]{3,1,5,6,4,2})); // 60
    }
}
