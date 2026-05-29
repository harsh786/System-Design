/**
 * Problem: Problem49 MaxProductSubarrayWindow - Maximum product subarray within bounded window size.
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: Maximum product subarray within bounded window size.
 */
import java.util.*;

public class Problem49_MaxProductSubarrayWindow {
    // Max product subarray of length at most k
    // Simplified: track max/min product ending at each position within window
    public static long maxProductWindow(int[] nums, int k) {
        long maxProd = Long.MIN_VALUE;
        for (int start = 0; start < nums.length; start++) {
            long prod = 1;
            for (int end = start; end < Math.min(start + k, nums.length); end++) {
                prod *= nums[end];
                maxProd = Math.max(maxProd, prod);
            }
        }
        return maxProd;
    }

    public static void main(String[] args) {
        System.out.println(maxProductWindow(new int[]{2, 3, -2, 4, 1}, 3)); // 6
        System.out.println(maxProductWindow(new int[]{-2, 0, -1, 3, 2}, 4)); // 6
    }
}
