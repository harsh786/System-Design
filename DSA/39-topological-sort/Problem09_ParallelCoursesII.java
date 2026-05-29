import java.util.*;

/**
 * Problem: Parallel Courses II
 * Minimum semesters with at most k courses per semester.
 *
 * Approach: Bitmask DP - enumerate subsets of available courses of size <= k
 *
 * Time Complexity: O(3^n) for subset enumeration
 * Space Complexity: O(2^n)
 *
 * Production Analogy: Scheduling parallel CI/CD pipelines with resource constraints.
 */
public class Problem09_ParallelCoursesII {

    public int minNumberOfSemesters(int n, int[][] relations, int k) {
        int[] prereq = new int[n];
        for (int[] r : relations) prereq[r[1] - 1] |= (1 << (r[0] - 1));

        int[] dp = new int[1 << n];
        Arrays.fill(dp, n + 1);
        dp[0] = 0;

        for (int mask = 0; mask < (1 << n); mask++) {
            if (dp[mask] == n + 1) continue;
            int available = 0;
            for (int i = 0; i < n; i++)
                if ((mask & (1 << i)) == 0 && (prereq[i] & mask) == prereq[i])
                    available |= (1 << i);

            // Enumerate subsets of available with size <= k
            for (int sub = available; sub > 0; sub = (sub - 1) & available) {
                if (Integer.bitCount(sub) <= k)
                    dp[mask | sub] = Math.min(dp[mask | sub], dp[mask] + 1);
            }
        }
        return dp[(1 << n) - 1];
    }

    public static void main(String[] args) {
        Problem09_ParallelCoursesII solver = new Problem09_ParallelCoursesII();
        System.out.println(solver.minNumberOfSemesters(4, new int[][]{{2,1},{3,1},{1,4}}, 2)); // 3
    }
}
