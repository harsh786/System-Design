/**
 * Problem 3: Subarray Sum Equals K (LeetCode 560)
 * 
 * Pattern: Prefix sum + HashMap to count subarrays with target sum
 * 
 * Key insight: If prefix[j] - prefix[i] == k, then subarray (i,j] sums to k.
 * Store frequency of each prefix sum seen so far in a map.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Finding time windows where exactly K errors occurred
 * in a cumulative error counter stream.
 */
import java.util.*;

public class Problem03_SubarraySumEqualsK {

    public static int subarraySum(int[] nums, int k) {
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
        assert subarraySum(new int[]{1, 1, 1}, 2) == 2;
        assert subarraySum(new int[]{1, 2, 3}, 3) == 2;
        assert subarraySum(new int[]{1}, 0) == 0;
        assert subarraySum(new int[]{0, 0, 0}, 0) == 6;
        assert subarraySum(new int[]{-1, -1, 1}, 0) == 1;
        System.out.println("All tests passed!");
    }
}
