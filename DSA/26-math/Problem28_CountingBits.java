/**
 * Problem 28: Counting Bits
 * For every number 0..n, count the number of 1s in binary representation.
 *
 * Approach: DP - dp[i] = dp[i >> 1] + (i & 1). Or dp[i] = dp[i & (i-1)] + 1.
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 *
 * Production Analogy: Like precomputing popcount tables for SIMD operations
 * in high-performance data processing.
 */
import java.util.Arrays;

public class Problem28_CountingBits {

    public static int[] countBits(int n) {
        int[] dp = new int[n + 1];
        for (int i = 1; i <= n; i++) {
            dp[i] = dp[i >> 1] + (i & 1);
        }
        return dp;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(countBits(5)));  // [0,1,1,2,1,2]
        System.out.println(Arrays.toString(countBits(2)));  // [0,1,1]
        System.out.println(Arrays.toString(countBits(0)));  // [0]
    }
}
