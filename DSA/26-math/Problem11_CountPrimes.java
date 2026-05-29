/**
 * Problem 11: Count Primes (Sieve of Eratosthenes)
 * Count the number of prime numbers less than n.
 *
 * Approach: Sieve of Eratosthenes - mark composites starting from each prime.
 * Time Complexity: O(n log log n)
 * Space Complexity: O(n)
 *
 * Production Analogy: Like precomputing lookup tables for cryptographic
 * prime generation or hash function design.
 */
public class Problem11_CountPrimes {

    public static int countPrimes(int n) {
        if (n <= 2) return 0;
        boolean[] notPrime = new boolean[n];
        int count = 0;
        for (int i = 2; i < n; i++) {
            if (!notPrime[i]) {
                count++;
                if ((long) i * i < n) {
                    for (int j = i * i; j < n; j += i) {
                        notPrime[j] = true;
                    }
                }
            }
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(countPrimes(10));       // 4
        System.out.println(countPrimes(0));        // 0
        System.out.println(countPrimes(1));        // 0
        System.out.println(countPrimes(2));        // 0
        System.out.println(countPrimes(100));      // 25
        System.out.println(countPrimes(1000000));  // 78498
    }
}
