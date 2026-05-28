import java.util.*;

/**
 * Problem 7: Subarray Sum Equals K
 * Find the total number of continuous subarrays whose sum equals k.
 *
 * Approach: Prefix sum + HashMap. Store prefix_sum -> count of occurrences.
 * If prefixSum - k exists in map, those are valid subarrays ending at current index.
 *
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 *
 * Production Analogy: Finding time ranges where cumulative metrics hit a target -
 * like detecting network usage windows that sum to a billing threshold.
 */
public class Problem07_SubarraySumEqualsK {
    public int subarraySum(int[] nums, int k) {
        Map<Integer, Integer> prefixCount = new HashMap<>();
        prefixCount.put(0, 1); // empty prefix
        int sum = 0, count = 0;
        for (int num : nums) {
            sum += num;
            count += prefixCount.getOrDefault(sum - k, 0);
            prefixCount.merge(sum, 1, Integer::sum);
        }
        return count;
    }

    public static void main(String[] args) {
        Problem07_SubarraySumEqualsK sol = new Problem07_SubarraySumEqualsK();
        System.out.println(sol.subarraySum(new int[]{1,1,1}, 2)); // 2
        System.out.println(sol.subarraySum(new int[]{1,2,3}, 3)); // 2
        System.out.println(sol.subarraySum(new int[]{1,-1,0}, 0)); // 3
        System.out.println(sol.subarraySum(new int[]{-1,-1,1}, 0)); // 1
    }
}
