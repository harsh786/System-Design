/**
 * Problem 5: Counting Bits
 * For every number in [0, n], count set bits.
 * 
 * Approach: dp[i] = dp[i >> 1] + (i & 1). Right shift reuses previous result.
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Precomputing permission complexity scores for all role bitmasks.
 */
public class Problem05_CountingBits {
    public static int[] countBits(int n) {
        int[] dp = new int[n + 1];
        for (int i = 1; i <= n; i++) {
            dp[i] = dp[i >> 1] + (i & 1);
        }
        return dp;
    }

    public static void main(String[] args) {
        int[] r = countBits(5);
        for (int v : r) System.out.print(v + " "); // 0 1 1 2 1 2
        System.out.println();
        r = countBits(0);
        for (int v : r) System.out.print(v + " "); // 0
        System.out.println();
    }
}
