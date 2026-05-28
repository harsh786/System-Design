import java.util.*;

/**
 * Problem 40: The Number of Beautiful Subsets (LeetCode 2597)
 * 
 * Count non-empty subsets where no two elements have absolute difference equal to k.
 * 
 * Search Tree:
 * - Subset enumeration: include/exclude each element
 * - Check if adding element conflicts with any existing element in subset
 * 
 * Pruning Strategy:
 * - Sort array; when including nums[i], check if (nums[i]-k) is in current subset
 * - Use a frequency map for O(1) conflict detection
 * 
 * Time Complexity: O(2^n)
 * Space Complexity: O(n)
 * 
 * Production Analogy:
 * - Selecting non-conflicting time slots: no two selected slots within k minutes of each other.
 */
public class Problem40_NumberOfBeautifulSubsets {

    private int count;

    public int beautifulSubsets(int[] nums, int k) {
        count = 0;
        Arrays.sort(nums);
        backtrack(nums, k, 0, new HashMap<>());
        return count; // subtract 0 since we skip empty set
    }

    private void backtrack(int[] nums, int k, int idx, Map<Integer, Integer> freq) {
        if (idx == nums.length) {
            if (!freq.isEmpty()) count++;
            return;
        }
        // Exclude
        backtrack(nums, k, idx + 1, freq);
        // Include if no conflict
        if (!freq.containsKey(nums[idx] - k)) {
            freq.merge(nums[idx], 1, Integer::sum);
            backtrack(nums, k, idx + 1, freq);
            if (freq.get(nums[idx]) == 1) freq.remove(nums[idx]);
            else freq.merge(nums[idx], -1, Integer::sum);
        }
    }

    public static void main(String[] args) {
        Problem40_NumberOfBeautifulSubsets sol = new Problem40_NumberOfBeautifulSubsets();

        System.out.println(sol.beautifulSubsets(new int[]{2,4,6}, 2)); // 4
        System.out.println(sol.beautifulSubsets(new int[]{1}, 1));     // 1
        System.out.println(sol.beautifulSubsets(new int[]{1,2,3,3}, 1)); 
    }
}
