import java.util.*;

/**
 * Problem 3: Permutations (LeetCode 46)
 * 
 * Given an array of distinct integers, return all possible permutations.
 * 
 * Search Tree:
 * - At each level, choose any unused element -> n choices at level 0, n-1 at level 1, etc.
 * - Total leaf nodes: n!
 * 
 * Pruning Strategy:
 * - Use a boolean[] used array to track which elements are already in the current permutation
 * - No further pruning needed since all permutations are valid
 * 
 * Time Complexity: O(n! * n)
 * Space Complexity: O(n) for recursion + used array
 * 
 * Production Analogy:
 * - Task scheduling: enumerate all possible orderings of n independent tasks to find optimal execution order.
 */
public class Problem03_Permutations {

    public List<List<Integer>> permute(int[] nums) {
        List<List<Integer>> result = new ArrayList<>();
        backtrack(nums, new boolean[nums.length], new ArrayList<>(), result);
        return result;
    }

    private void backtrack(int[] nums, boolean[] used, List<Integer> current, List<List<Integer>> result) {
        if (current.size() == nums.length) {
            result.add(new ArrayList<>(current));
            return;
        }
        for (int i = 0; i < nums.length; i++) {
            if (used[i]) continue;
            used[i] = true;
            current.add(nums[i]);
            backtrack(nums, used, current, result);
            current.remove(current.size() - 1);
            used[i] = false;
        }
    }

    public static void main(String[] args) {
        Problem03_Permutations sol = new Problem03_Permutations();

        System.out.println(sol.permute(new int[]{1, 2, 3}));
        System.out.println(sol.permute(new int[]{0, 1}));
        System.out.println(sol.permute(new int[]{1}));
    }
}
