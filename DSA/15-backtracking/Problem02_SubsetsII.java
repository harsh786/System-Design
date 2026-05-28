import java.util.*;

/**
 * Problem 2: Subsets II (LeetCode 90)
 * 
 * Given an integer array that may contain duplicates, return all possible unique subsets.
 * 
 * Search Tree:
 * - Same as Subsets but with duplicate skipping at each level
 * - Sort array first, then skip nums[i] == nums[i-1] at same recursion level
 * 
 * Pruning Strategy:
 * - Sort + skip duplicates at same level: if nums[i] == nums[i-1] and i > start, skip
 * - This ensures we don't generate duplicate subsets
 * 
 * Time Complexity: O(n * 2^n) worst case
 * Space Complexity: O(n) recursion depth
 * 
 * Production Analogy:
 * - Deduplicating configuration combinations when multiple services have identical settings.
 */
public class Problem02_SubsetsII {

    public List<List<Integer>> subsetsWithDup(int[] nums) {
        List<List<Integer>> result = new ArrayList<>();
        Arrays.sort(nums);
        backtrack(nums, 0, new ArrayList<>(), result);
        return result;
    }

    private void backtrack(int[] nums, int start, List<Integer> current, List<List<Integer>> result) {
        result.add(new ArrayList<>(current));
        for (int i = start; i < nums.length; i++) {
            // Skip duplicates at the same decision level
            if (i > start && nums[i] == nums[i - 1]) continue;
            current.add(nums[i]);
            backtrack(nums, i + 1, current, result);
            current.remove(current.size() - 1);
        }
    }

    public static void main(String[] args) {
        Problem02_SubsetsII sol = new Problem02_SubsetsII();

        System.out.println(sol.subsetsWithDup(new int[]{1, 2, 2}));
        // Expected: [[], [1], [1,2], [1,2,2], [2], [2,2]]

        System.out.println(sol.subsetsWithDup(new int[]{0}));
        // Expected: [[], [0]]

        System.out.println(sol.subsetsWithDup(new int[]{4, 4, 4, 1, 4}));

        System.out.println(sol.subsetsWithDup(new int[]{}));
        // Expected: [[]]
    }
}
