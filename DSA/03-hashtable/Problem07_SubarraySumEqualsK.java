import java.util.*;

/**
 * Problem 7: Subarray Sum Equals K
 * Given an array of integers and k, find total number of continuous subarrays whose sum equals k.
 *
 * Approach: Prefix sum with HashMap. Store count of each prefix sum.
 * If prefixSum - k exists in map, those many subarrays end at current index.
 *
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 *
 * Production Analogy: Like cumulative metric analysis in monitoring systems.
 * Finding time windows where a metric changed by exactly X amount.
 */
public class Problem07_SubarraySumEqualsK {
    public int subarraySum(int[] nums, int k) {
        Map<Integer, Integer> prefixCount = new HashMap<>();
        prefixCount.put(0, 1);
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
