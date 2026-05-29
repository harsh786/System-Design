package numbertheory;

import java.util.*;

/**
 * Problem 49: Sieve of Eratosthenes Optimized (Segmented Sieve)
 * 
 * Approach: Use segmented sieve for better cache performance.
 * Sieve small primes up to sqrt(n), then process segments.
 * 
 * Time Complexity: O(n log log n)
 * Space Complexity: O(sqrt(n)) for the small primes sieve
 */
public class Problem49_SieveOfEratosthenesOptimized {
    
    public List<Integer> segmentedSieve(int n) {
        int sqrtN = (int) Math.sqrt(n);
        // Simple sieve up to sqrt(n)
        boolean[] isComposite = new boolean[sqrtN + 1];
        List<Integer> smallPrimes = new ArrayList<>();
        for (int i = 2; i <= sqrtN; i++) {
            if (!isComposite[i]) {
                smallPrimes.add(i);
                for (int j = i * i; j <= sqrtN; j += i) isComposite[j] = true;
            }
        }
        
        List<Integer> primes = new ArrayList<>(smallPrimes);
        int segSize = Math.max(sqrtN, 1);
        boolean[] seg = new boolean[segSize];
        
        for (int lo = sqrtN + 1; lo <= n; lo += segSize) {
            int hi = Math.min(lo + segSize - 1, n);
            Arrays.fill(seg, 0, hi - lo + 1, false);
            for (int p : smallPrimes) {
                int start = ((lo + p - 1) / p) * p;
                for (int j = start; j <= hi; j += p) seg[j - lo] = true;
            }
            for (int i = 0; i <= hi - lo; i++) if (!seg[i]) primes.add(lo + i);
        }
        return primes;
    }
    
    public static void main(String[] args) {
        Problem49_SieveOfEratosthenesOptimized sol = new Problem49_SieveOfEratosthenesOptimized();
        List<Integer> primes = sol.segmentedSieve(50);
        System.out.println(primes); // [2,3,5,7,11,13,17,19,23,29,31,37,41,43,47]
        System.out.println("Count: " + primes.size()); // 15
    }
}
