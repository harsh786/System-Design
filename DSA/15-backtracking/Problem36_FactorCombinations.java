import java.util.*;

/**
 * Problem 36: Factor Combinations (LeetCode 254)
 * 
 * Find all ways to factor a number into factors > 1 (excluding n = n*1).
 * 
 * Search Tree:
 * - At each step, try factors from start to sqrt(n)
 * - If f divides n, recurse with n/f and start=f
 * 
 * Pruning Strategy:
 * - Start from previous factor (avoid duplicates like 2*6 and 6*2)
 * - Only try factors up to sqrt(remaining) or remaining itself
 * 
 * Time Complexity: O(2^(log n)) approximately
 * Space Complexity: O(log n)
 * 
 * Production Analogy:
 * - Finding all possible ways to decompose a batch size into sub-batches for parallel processing.
 */
public class Problem36_FactorCombinations {

    public List<List<Integer>> getFactors(int n) {
        List<List<Integer>> result = new ArrayList<>();
        backtrack(n, 2, new ArrayList<>(), result);
        return result;
    }

    private void backtrack(int n, int start, List<Integer> factors, List<List<Integer>> result) {
        if (n == 1) {
            if (factors.size() > 1) result.add(new ArrayList<>(factors));
            return;
        }
        for (int f = start; f <= n; f++) {
            if (f > n / f && f != n) continue; // optimization: skip f > sqrt(n) unless f == n
            if (n % f != 0) continue;
            factors.add(f);
            backtrack(n / f, f, factors, result);
            factors.remove(factors.size() - 1);
        }
    }

    public static void main(String[] args) {
        Problem36_FactorCombinations sol = new Problem36_FactorCombinations();

        System.out.println(sol.getFactors(12)); // [[2,2,3],[2,6],[3,4]]
        System.out.println(sol.getFactors(1));  // []
        System.out.println(sol.getFactors(37)); // [] (prime)
        System.out.println(sol.getFactors(32)); // [[2,2,2,2,2],[2,2,2,4],[2,2,8],[2,4,4],[2,16],[4,8]]
    }
}
