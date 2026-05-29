package numbertheory;

/**
 * Problem 1: Count Primes (LeetCode 204) - Sieve of Eratosthenes
 * 
 * Approach: Mark composites in boolean array up to n.
 * 
 * Time Complexity: O(n log log n)
 * Space Complexity: O(n)
 */
public class Problem01_CountPrimesSieve {
    
    public int countPrimes(int n) {
        if (n <= 2) return 0;
        boolean[] notPrime = new boolean[n];
        int count = 0;
        for (int i = 2; i < n; i++) {
            if (!notPrime[i]) {
                count++;
                if ((long) i * i < n) {
                    for (int j = i * i; j < n; j += i) notPrime[j] = true;
                }
            }
        }
        return count;
    }
    
    public static void main(String[] args) {
        Problem01_CountPrimesSieve sol = new Problem01_CountPrimesSieve();
        System.out.println(sol.countPrimes(10));  // 4
        System.out.println(sol.countPrimes(100)); // 25
    }
}
