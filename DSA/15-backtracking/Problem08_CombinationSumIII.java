import java.util.*;

/**
 * Problem 8: Combination Sum III (LeetCode 216)
 * 
 * Find all valid combinations of k numbers that sum to n, using numbers 1-9 each at most once.
 * 
 * Search Tree:
 * - Choose k numbers from [1..9] that sum to n
 * - At each step pick from [start..9]
 * 
 * Pruning Strategy:
 * - If remaining < 0, stop
 * - If current.size() == k and remaining != 0, stop
 * - If candidate > remaining, break (since sorted ascending)
 * 
 * Time Complexity: O(C(9,k) * k)
 * Space Complexity: O(k)
 * 
 * Production Analogy:
 * - Selecting exactly k microservices from 9 available that together consume exactly n units of memory.
 */
public class Problem08_CombinationSumIII {

    public List<List<Integer>> combinationSum3(int k, int n) {
        List<List<Integer>> result = new ArrayList<>();
        backtrack(k, n, 1, new ArrayList<>(), result);
        return result;
    }

    private void backtrack(int k, int remaining, int start, List<Integer> current, List<List<Integer>> result) {
        if (current.size() == k) {
            if (remaining == 0) result.add(new ArrayList<>(current));
            return;
        }
        for (int i = start; i <= 9; i++) {
            if (i > remaining) break;
            current.add(i);
            backtrack(k, remaining - i, i + 1, current, result);
            current.remove(current.size() - 1);
        }
    }

    public static void main(String[] args) {
        Problem08_CombinationSumIII sol = new Problem08_CombinationSumIII();

        System.out.println(sol.combinationSum3(3, 7));  // [[1,2,4]]
        System.out.println(sol.combinationSum3(3, 9));  // [[1,2,6],[1,3,5],[2,3,4]]
        System.out.println(sol.combinationSum3(4, 1));  // []
        System.out.println(sol.combinationSum3(2, 17)); // [[8,9]]
    }
}
