import java.util.*;

/**
 * Problem 39: Count Number of Maximum Bitwise-OR Subsets (LeetCode 2044)
 * 
 * Find the number of subsets that achieve the maximum possible bitwise OR.
 * 
 * Search Tree:
 * - Subset generation: include/exclude each element
 * - Track OR value; count subsets matching max OR
 * 
 * Pruning Strategy:
 * - First compute max OR (OR of all elements)
 * - During backtracking, if current OR already equals max, all subsets including remaining are valid
 *   (since OR is monotonically non-decreasing with more elements)
 * 
 * Time Complexity: O(2^n)
 * Space Complexity: O(n)
 * 
 * Production Analogy:
 * - Feature flag coverage: counting how many combinations of enabled features achieve full capability coverage.
 */
public class Problem39_CountMaxBitwiseORSubsets {

    private int count;

    public int countMaxOrSubsets(int[] nums) {
        int maxOr = 0;
        for (int n : nums) maxOr |= n;
        count = 0;
        backtrack(nums, 0, 0, maxOr);
        return count;
    }

    private void backtrack(int[] nums, int idx, int currentOr, int maxOr) {
        if (currentOr == maxOr) {
            // All subsets from here (2^remaining) are valid
            count += (1 << (nums.length - idx));
            return;
        }
        if (idx == nums.length) return;
        // Exclude nums[idx]
        backtrack(nums, idx + 1, currentOr, maxOr);
        // Include nums[idx]
        backtrack(nums, idx + 1, currentOr | nums[idx], maxOr);
    }

    public static void main(String[] args) {
        Problem39_CountMaxBitwiseORSubsets sol = new Problem39_CountMaxBitwiseORSubsets();

        System.out.println(sol.countMaxOrSubsets(new int[]{3,1}));     // 2
        System.out.println(sol.countMaxOrSubsets(new int[]{2,2,2}));   // 7
        System.out.println(sol.countMaxOrSubsets(new int[]{3,2,1,5})); // 6
    }
}
