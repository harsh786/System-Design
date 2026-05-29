/**
 * Problem: Count Primes (LeetCode 204) - Sieve of Eratosthenes
 * Approach: Mark composites using sieve
 * Complexity: O(n log log n) time, O(n) space
 * Production Analogy: Pre-computation tables for cryptographic key generation
 */
public class Problem17_CountPrimes {
    public int countPrimes(int n) {
        if (n <= 2) return 0;
        boolean[] notPrime = new boolean[n];
        int count = 0;
        for (int i = 2; i < n; i++) {
            if (!notPrime[i]) {
                count++;
                for (long j = (long)i*i; j < n; j += i) notPrime[(int)j] = true;
            }
        }
        return count;
    }
    public static void main(String[] args) {
        System.out.println(new Problem17_CountPrimes().countPrimes(10)); // 4
    }
}
