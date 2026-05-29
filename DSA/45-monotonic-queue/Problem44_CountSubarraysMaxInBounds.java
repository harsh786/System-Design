/**
 * Problem: Problem44 CountSubarraysMaxInBounds - Count subarrays where max is within [lo, hi] bounds.
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: Count subarrays where max is within [lo, hi] bounds.
 */
import java.util.*;

public class Problem44_CountSubarraysMaxInBounds {
    // Count subarrays where max element is in [lo, hi]
    // = count(max <= hi) - count(max <= lo - 1)
    private static long countMaxAtMost(int[] nums, int bound) {
        long count = 0;
        int left = 0;
        for (int right = 0; right < nums.length; right++) {
            if (nums[right] > bound) left = right + 1;
            count += right - left + 1;
        }
        return count;
    }

    public static long countSubarrays(int[] nums, int lo, int hi) {
        return countMaxAtMost(nums, hi) - countMaxAtMost(nums, lo - 1);
    }

    public static void main(String[] args) {
        System.out.println(countSubarrays(new int[]{2, 1, 4, 3}, 2, 3)); // 3: [2],[2,1],[3]
    }
}
