package numbertheory;

import java.util.*;

/**
 * Problem 4: Super Ugly Number (LeetCode 313)
 * 
 * Approach: Generalized ugly number with k primes. Use k pointers.
 * 
 * Time Complexity: O(n * k)
 * Space Complexity: O(n + k)
 */
public class Problem04_SuperUglyNumber {
    
    public int nthSuperUglyNumber(int n, int[] primes) {
        int k = primes.length;
        int[] idx = new int[k];
        long[] ugly = new long[n];
        ugly[0] = 1;
        for (int i = 1; i < n; i++) {
            long min = Long.MAX_VALUE;
            for (int j = 0; j < k; j++) min = Math.min(min, ugly[idx[j]] * primes[j]);
            ugly[i] = min;
            for (int j = 0; j < k; j++) if (ugly[idx[j]] * primes[j] == min) idx[j]++;
        }
        return (int) ugly[n - 1];
    }
    
    public static void main(String[] args) {
        Problem04_SuperUglyNumber sol = new Problem04_SuperUglyNumber();
        System.out.println(sol.nthSuperUglyNumber(12, new int[]{2, 7, 13, 19})); // 32
    }
}
