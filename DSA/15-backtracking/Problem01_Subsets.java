import java.util.*;

/**
 * Problem 1: Subsets (LeetCode 78)
 * 
 * Given an integer array of unique elements, return all possible subsets (power set).
 * 
 * Search Tree:
 * - At each index, we decide: include nums[i] or skip nums[i]
 * - Tree has depth n, each node has 2 branches -> 2^n leaf nodes
 * 
 * Pruning Strategy:
 * - No pruning needed since we want ALL subsets
 * - We only iterate forward (start index) to avoid duplicates
 * 
 * Time Complexity: O(n * 2^n) - 2^n subsets, each takes O(n) to copy
 * Space Complexity: O(n) recursion depth + O(n * 2^n) for output
 * 
 * Production Analogy:
 * - Feature flag combinations: given n independent feature flags, enumerate all
 *   possible configurations for integration testing.
 */
public class Problem01_Subsets {

    public List<List<Integer>> subsets(int[] nums) {
        List<List<Integer>> result = new ArrayList<>();
        backtrack(nums, 0, new ArrayList<>(), result);
        return result;
    }

    private void backtrack(int[] nums, int start, List<Integer> current, List<List<Integer>> result) {
        result.add(new ArrayList<>(current)); // every node is a valid subset
        for (int i = start; i < nums.length; i++) {
            current.add(nums[i]);
            backtrack(nums, i + 1, current, result);
            current.remove(current.size() - 1); // undo choice
        }
    }

    public static void main(String[] args) {
        Problem01_Subsets sol = new Problem01_Subsets();

        // Test 1: Normal case
        System.out.println(sol.subsets(new int[]{1, 2, 3}));
        // Expected: [[], [1], [1,2], [1,2,3], [1,3], [2], [2,3], [3]]

        // Test 2: Single element
        System.out.println(sol.subsets(new int[]{0}));
        // Expected: [[], [0]]

        // Test 3: Empty array
        System.out.println(sol.subsets(new int[]{}));
        // Expected: [[]]

        // Test 4: Two elements
        System.out.println(sol.subsets(new int[]{5, 9}));
        // Expected: [[], [5], [5,9], [9]]
    }
}
