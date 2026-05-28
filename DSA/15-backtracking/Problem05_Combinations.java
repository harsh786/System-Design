import java.util.*;

/**
 * Problem 5: Combinations (LeetCode 77)
 * 
 * Given two integers n and k, return all possible combinations of k numbers chosen from [1, n].
 * 
 * Search Tree:
 * - At each step, pick the next number from [start, n]
 * - Stop when current list has k elements
 * 
 * Pruning Strategy:
 * - If remaining elements (n - i + 1) < elements needed (k - current.size()), prune
 * - i.e., loop from start to n - (k - current.size()) + 1
 * 
 * Time Complexity: O(C(n,k) * k)
 * Space Complexity: O(k) recursion depth
 * 
 * Production Analogy:
 * - Selecting k servers from n available for a quorum-based consensus protocol.
 */
public class Problem05_Combinations {

    public List<List<Integer>> combine(int n, int k) {
        List<List<Integer>> result = new ArrayList<>();
        backtrack(n, k, 1, new ArrayList<>(), result);
        return result;
    }

    private void backtrack(int n, int k, int start, List<Integer> current, List<List<Integer>> result) {
        if (current.size() == k) {
            result.add(new ArrayList<>(current));
            return;
        }
        // Pruning: need (k - current.size()) more elements, so i can go up to n - need + 1
        for (int i = start; i <= n - (k - current.size()) + 1; i++) {
            current.add(i);
            backtrack(n, k, i + 1, current, result);
            current.remove(current.size() - 1);
        }
    }

    public static void main(String[] args) {
        Problem05_Combinations sol = new Problem05_Combinations();

        System.out.println(sol.combine(4, 2));
        System.out.println(sol.combine(1, 1));
        System.out.println(sol.combine(5, 3));
    }
}
