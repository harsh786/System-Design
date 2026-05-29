/**
 * Problem 50: Sieve of Eratosthenes (Optimized)
 * Find all primes up to n with optimizations: skip evens, bitset, segmented sieve.
 *
 * Approach:
 * 1. Only store odd numbers (halve memory)
 * 2. Start marking from p*p
 * 3. Segmented sieve for very large ranges (cache-friendly)
 * Time Complexity: O(n log log n)
 * Space Complexity: O(n/16) with bitset for odds only
 *
 * Production Analogy: Like building bloom filters or hash tables with prime-sized
 * buckets. Segmented approach mirrors cache-aware algorithms in databases.
 */
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public class Problem50_SieveOfEratosthenesOptimized {

    // Optimized: only odd numbers, using bitset
    public static List<Integer> sieveOptimized(int n) {
        List<Integer> primes = new ArrayList<>();
        if (n < 2) return primes;
        primes.add(2);
        if (n == 2) return primes;

        // isComposite[i] represents number 2*i + 1
        int size = (n - 1) / 2;
        boolean[] isComposite = new boolean[size + 1];

        for (int i = 1; i <= size; i++) {
            if (!isComposite[i]) {
                int prime = 2 * i + 1;
                primes.add(prime);
                // Mark composites starting from prime*prime
                long start = (long) prime * prime;
                if (start > n) continue;
                // prime*prime is odd, step by 2*prime to stay on odd numbers
                for (long j = (start - 1) / 2; j <= size; j += prime) {
                    isComposite[(int) j] = true;
                }
            }
        }
        return primes;
    }

    // Segmented sieve for range [lo, hi]
    public static List<Integer> segmentedSieve(int lo, int hi) {
        int sqrtHi = (int) Math.sqrt(hi) + 1;
        // Get small primes
        List<Integer> smallPrimes = sieveOptimized(sqrtHi);

        boolean[] isComposite = new boolean[hi - lo + 1];

        for (int p : smallPrimes) {
            int start = (int) (Math.ceil((double) lo / p) * p);
            if (start == p) start += p; // don't mark prime itself
            for (int j = start; j <= hi; j += p) {
                isComposite[j - lo] = true;
            }
        }

        List<Integer> result = new ArrayList<>();
        for (int i = 0; i < isComposite.length; i++) {
            if (!isComposite[i] && (i + lo) >= 2) {
                result.add(i + lo);
            }
        }
        return result;
    }

    public static void main(String[] args) {
        List<Integer> primes = sieveOptimized(50);
        System.out.println("Primes up to 50: " + primes);
        System.out.println("Count of primes up to 1000000: " + sieveOptimized(1000000).size()); // 78498

        List<Integer> segmented = segmentedSieve(100, 150);
        System.out.println("Primes in [100,150]: " + segmented);
        // [101, 103, 107, 109, 113, 127, 131, 137, 139, 149]

        // Edge cases
        System.out.println("Primes up to 2: " + sieveOptimized(2));   // [2]
        System.out.println("Primes up to 1: " + sieveOptimized(1));   // []
    }
}
