import java.util.*;

/**
 * Problem 18: Beautiful Arrangement (LeetCode 526)
 * 
 * Count permutations of 1..n where perm[i] % i == 0 or i % perm[i] == 0 for all i.
 * 
 * Search Tree:
 * - At position i, try all unused numbers that satisfy the divisibility condition
 * 
 * Pruning Strategy:
 * - Only try numbers that satisfy perm[i] % i == 0 || i % perm[i] == 0
 * - This dramatically reduces branches compared to trying all unused numbers
 * 
 * Time Complexity: O(k) where k = number of valid permutations (much less than n!)
 * Space Complexity: O(n)
 * 
 * Production Analogy:
 * - Constraint-based task assignment: assigning workers to slots where compatibility is required.
 */
public class Problem18_BeautifulArrangement {

    private int count;

    public int countArrangement(int n) {
        count = 0;
        backtrack(n, 1, new boolean[n + 1]);
        return count;
    }

    private void backtrack(int n, int pos, boolean[] used) {
        if (pos > n) { count++; return; }
        for (int num = 1; num <= n; num++) {
            if (used[num]) continue;
            if (num % pos != 0 && pos % num != 0) continue; // pruning
            used[num] = true;
            backtrack(n, pos + 1, used);
            used[num] = false;
        }
    }

    public static void main(String[] args) {
        Problem18_BeautifulArrangement sol = new Problem18_BeautifulArrangement();

        System.out.println(sol.countArrangement(2));  // 2
        System.out.println(sol.countArrangement(1));  // 1
        System.out.println(sol.countArrangement(6));  // 36
        System.out.println(sol.countArrangement(15)); // 24679
    }
}
