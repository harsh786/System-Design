/**
 * Problem: Counting Bits (LeetCode 338)
 * Approach: DP - dp[i] = dp[i>>1] + (i&1)
 * Complexity: O(n) time, O(n) space
 * Production Analogy: Precomputing popcount tables for SIMD operations
 */
import java.util.*;
public class Problem18_CountingBits {
    public int[] countBits(int n) {
        int[] dp = new int[n+1];
        for (int i = 1; i <= n; i++) dp[i] = dp[i>>1] + (i&1);
        return dp;
    }
    public static void main(String[] args) {
        System.out.println(Arrays.toString(new Problem18_CountingBits().countBits(5))); // [0,1,1,2,1,2]
    }
}
