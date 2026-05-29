/**
 * Problem 41: Beautiful Arrangement
 * Count permutations of [1..n] where perm[i] % i == 0 or i % perm[i] == 0.
 * 
 * Approach: Bitmask DP. mask = set of numbers used. Position = popcount(mask).
 * Time: O(2^n * n), Space: O(2^n)
 * 
 * Production Analogy: Counting valid task-to-worker assignments with compatibility constraints.
 */
public class Problem41_BeautifulArrangement {
    public static int countArrangement(int n) {
        int[] dp = new int[1 << n];
        dp[0] = 1;
        for (int mask = 0; mask < (1 << n); mask++) {
            if (dp[mask] == 0) continue;
            int pos = Integer.bitCount(mask) + 1; // next position to fill
            for (int i = 0; i < n; i++) {
                if ((mask & (1 << i)) != 0) continue;
                int num = i + 1;
                if (num % pos == 0 || pos % num == 0) {
                    dp[mask | (1 << i)] += dp[mask];
                }
            }
        }
        return dp[(1 << n) - 1];
    }

    public static void main(String[] args) {
        System.out.println(countArrangement(2)); // 2
        System.out.println(countArrangement(3)); // 3
        System.out.println(countArrangement(1)); // 1
    }
}
