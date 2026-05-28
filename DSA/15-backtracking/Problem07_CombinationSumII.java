import java.util.*;

/**
 * Problem 7: Combination Sum II (LeetCode 40)
 * 
 * Find all unique combinations where candidates sum to target. Each number used once.
 * 
 * Search Tree:
 * - Sort + skip duplicates at same level (i > start && nums[i] == nums[i-1])
 * - Move to i+1 after picking (no reuse)
 * 
 * Pruning Strategy:
 * - Sort and break when candidate > remaining
 * - Skip duplicate values at same recursion level
 * 
 * Time Complexity: O(2^n * n)
 * Space Complexity: O(n)
 * 
 * Production Analogy:
 * - Budget allocation: select distinct expense items (with duplicates in catalog) summing to budget.
 */
public class Problem07_CombinationSumII {

    public List<List<Integer>> combinationSum2(int[] candidates, int target) {
        List<List<Integer>> result = new ArrayList<>();
        Arrays.sort(candidates);
        backtrack(candidates, target, 0, new ArrayList<>(), result);
        return result;
    }

    private void backtrack(int[] candidates, int remaining, int start, List<Integer> current, List<List<Integer>> result) {
        if (remaining == 0) {
            result.add(new ArrayList<>(current));
            return;
        }
        for (int i = start; i < candidates.length; i++) {
            if (candidates[i] > remaining) break;
            if (i > start && candidates[i] == candidates[i - 1]) continue;
            current.add(candidates[i]);
            backtrack(candidates, remaining - candidates[i], i + 1, current, result);
            current.remove(current.size() - 1);
        }
    }

    public static void main(String[] args) {
        Problem07_CombinationSumII sol = new Problem07_CombinationSumII();

        System.out.println(sol.combinationSum2(new int[]{10,1,2,7,6,1,5}, 8));
        // [[1,1,6],[1,2,5],[1,7],[2,6]]

        System.out.println(sol.combinationSum2(new int[]{2,5,2,1,2}, 5));
        // [[1,2,2],[5]]
    }
}
