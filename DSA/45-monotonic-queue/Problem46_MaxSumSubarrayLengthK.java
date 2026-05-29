/**
 * Problem: Problem46 MaxSumSubarrayLengthK - Maximum sum subarray of exactly length k (simple sliding window).
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: Maximum sum subarray of exactly length k (simple sliding window).
 */
import java.util.*;

public class Problem46_MaxSumSubarrayLengthK {
    public static int maxSumK(int[] nums, int k) {
        int sum = 0, maxSum;
        for (int i = 0; i < k; i++) sum += nums[i];
        maxSum = sum;
        for (int i = k; i < nums.length; i++) {
            sum += nums[i] - nums[i - k];
            maxSum = Math.max(maxSum, sum);
        }
        return maxSum;
    }

    public static void main(String[] args) {
        System.out.println(maxSumK(new int[]{1, 4, 2, 10, 2, 3, 1, 0, 20}, 4)); // 24
    }
}
