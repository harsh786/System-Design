import java.util.*;

/**
 * Problem 4: Permutations II (LeetCode 47)
 * 
 * Given a collection of numbers that might contain duplicates, return all unique permutations.
 * 
 * Search Tree:
 * - Same as Permutations but prune duplicate branches
 * - Sort first, then skip if nums[i]==nums[i-1] and !used[i-1]
 * 
 * Pruning Strategy:
 * - Sort array to group duplicates together
 * - Skip nums[i] if it equals nums[i-1] and nums[i-1] is not used (ensures we only pick
 *   the first occurrence of a duplicate at each level)
 * 
 * Time Complexity: O(n! * n) worst case, better with duplicates
 * Space Complexity: O(n)
 * 
 * Production Analogy:
 * - Generating unique deployment orderings when some services are identical replicas.
 */
public class Problem04_PermutationsII {

    public List<List<Integer>> permuteUnique(int[] nums) {
        List<List<Integer>> result = new ArrayList<>();
        Arrays.sort(nums);
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
            if (i > 0 && nums[i] == nums[i - 1] && !used[i - 1]) continue;
            used[i] = true;
            current.add(nums[i]);
            backtrack(nums, used, current, result);
            current.remove(current.size() - 1);
            used[i] = false;
        }
    }

    public static void main(String[] args) {
        Problem04_PermutationsII sol = new Problem04_PermutationsII();

        System.out.println(sol.permuteUnique(new int[]{1, 1, 2}));
        // [[1,1,2],[1,2,1],[2,1,1]]

        System.out.println(sol.permuteUnique(new int[]{1, 2, 3}));
        System.out.println(sol.permuteUnique(new int[]{2, 2, 2}));
        // [[2,2,2]]
    }
}
