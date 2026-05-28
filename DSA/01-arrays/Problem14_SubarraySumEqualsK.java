import java.util.*;

/**
 * Problem 14: Subarray Sum Equals K
 * Count number of continuous subarrays whose sum equals k.
 * 
 * Production Analogy: Like counting time windows where cumulative API calls hit a threshold -
 * prefix sum + hashmap to find windows matching a quota.
 * 
 * O(n) time, O(n) space - prefix sum with hashmap counting occurrences
 */
public class Problem14_SubarraySumEqualsK {

    public static int subarraySum(int[] nums, int k) {
        Map<Integer, Integer> prefixCount = new HashMap<>();
        prefixCount.put(0, 1);
        int sum = 0, count = 0;
        for (int n : nums) {
            sum += n;
            count += prefixCount.getOrDefault(sum - k, 0);
            prefixCount.merge(sum, 1, Integer::sum);
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(subarraySum(new int[]{1,1,1}, 2));      // 2
        System.out.println(subarraySum(new int[]{1,2,3}, 3));      // 2
        System.out.println(subarraySum(new int[]{1,-1,0}, 0));     // 3
        System.out.println(subarraySum(new int[]{-1,-1,1}, 0));    // 1
    }
}
