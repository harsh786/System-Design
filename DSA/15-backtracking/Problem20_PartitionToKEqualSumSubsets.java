import java.util.*;

/**
 * Problem 20: Partition to K Equal Sum Subsets (LeetCode 698)
 * 
 * Determine if array can be partitioned into k subsets with equal sum.
 * 
 * Search Tree:
 * - For each number, assign it to one of k buckets
 * - Generalization of Matchsticks to Square (k=4 -> general k)
 * 
 * Pruning Strategy:
 * - Sort descending for early failure
 * - Skip if bucket would overflow target
 * - Skip duplicate bucket values to avoid symmetric exploration
 * - If first element can't fit anywhere, fail fast
 * 
 * Time Complexity: O(k^n) worst case
 * Space Complexity: O(n)
 * 
 * Production Analogy:
 * - Sharding: distributing data evenly across k database shards.
 */
public class Problem20_PartitionToKEqualSumSubsets {

    public boolean canPartitionKSubsets(int[] nums, int k) {
        int sum = 0;
        for (int n : nums) sum += n;
        if (sum % k != 0) return false;
        int target = sum / k;
        Arrays.sort(nums);
        if (nums[nums.length - 1] > target) return false;
        // reverse
        for (int i = 0, j = nums.length - 1; i < j; i++, j--) {
            int t = nums[i]; nums[i] = nums[j]; nums[j] = t;
        }
        return backtrack(nums, new int[k], 0, target);
    }

    private boolean backtrack(int[] nums, int[] buckets, int idx, int target) {
        if (idx == nums.length) return true;
        for (int i = 0; i < buckets.length; i++) {
            if (buckets[i] + nums[idx] > target) continue;
            if (i > 0 && buckets[i] == buckets[i - 1]) continue;
            buckets[i] += nums[idx];
            if (backtrack(nums, buckets, idx + 1, target)) return true;
            buckets[i] -= nums[idx];
        }
        return false;
    }

    public static void main(String[] args) {
        Problem20_PartitionToKEqualSumSubsets sol = new Problem20_PartitionToKEqualSumSubsets();

        System.out.println(sol.canPartitionKSubsets(new int[]{4,3,2,3,5,2,1}, 4)); // true
        System.out.println(sol.canPartitionKSubsets(new int[]{1,2,3,4}, 3)); // false
    }
}
