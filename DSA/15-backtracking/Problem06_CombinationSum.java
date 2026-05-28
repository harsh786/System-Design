import java.util.*;

/**
 * Problem 6: Combination Sum (LeetCode 39)
 * 
 * Find all unique combinations where candidate numbers sum to target.
 * Each number may be used unlimited times.
 * 
 * Search Tree:
 * - At each level, try candidates[i..n-1], allowing reuse (start from i, not i+1)
 * - Branch when remaining target > 0
 * 
 * Pruning Strategy:
 * - Sort candidates; if candidates[i] > remaining, break (all subsequent are larger)
 * - Start index prevents generating duplicate combinations in different orders
 * 
 * Time Complexity: O(n^(T/M)) where T=target, M=min candidate
 * Space Complexity: O(T/M) recursion depth
 * 
 * Production Analogy:
 * - Resource allocation: find all ways to fill a fixed-size container using available package sizes.
 */
public class Problem06_CombinationSum {

    public List<List<Integer>> combinationSum(int[] candidates, int target) {
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
            if (candidates[i] > remaining) break; // pruning
            current.add(candidates[i]);
            backtrack(candidates, remaining - candidates[i], i, current, result); // i, not i+1 (reuse allowed)
            current.remove(current.size() - 1);
        }
    }

    public static void main(String[] args) {
        Problem06_CombinationSum sol = new Problem06_CombinationSum();

        System.out.println(sol.combinationSum(new int[]{2, 3, 6, 7}, 7));
        // [[2,2,3],[7]]

        System.out.println(sol.combinationSum(new int[]{2, 3, 5}, 8));
        System.out.println(sol.combinationSum(new int[]{2}, 1));
        // []
    }
}
