import java.util.*;
/**
 * Problem 47: Maximum Sum of Almost Unique Subarray (LeetCode 2841)
 * 
 * Approach: Fixed window of size k, track distinct count. Valid if distinct >= m.
 * Window invariant: window size == k, frequency map for distinct count.
 * 
 * Time: O(n), Space: O(k)
 * 
 * Production Analogy: Like finding the highest-value batch with sufficient diversity
 * (at least m categories) in recommendation systems.
 */
public class Problem47_MaximumSumOfAlmostUniqueSubarray {
    public static long maxSum(List<Integer> nums, int m, int k) {
        Map<Integer, Integer> freq = new HashMap<>();
        long sum = 0, maxSum = 0;
        for (int i = 0; i < nums.size(); i++) {
            sum += nums.get(i);
            freq.merge(nums.get(i), 1, Integer::sum);
            if (i >= k) {
                int old = nums.get(i - k);
                sum -= old;
                freq.merge(old, -1, Integer::sum);
                if (freq.get(old) == 0) freq.remove(old);
            }
            if (i >= k - 1 && freq.size() >= m) {
                maxSum = Math.max(maxSum, sum);
            }
        }
        return maxSum;
    }

    public static void main(String[] args) {
        System.out.println(maxSum(Arrays.asList(2,6,7,3,1,7), 3, 4)); // 18
        System.out.println(maxSum(Arrays.asList(5,9,9,2,4,5,4), 1, 3)); // 23
        System.out.println(maxSum(Arrays.asList(1,2,1,2,1,2,1), 3, 3)); // 0
    }
}
