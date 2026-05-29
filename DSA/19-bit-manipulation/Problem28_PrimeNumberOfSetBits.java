/**
 * Problem 28: Prime Number of Set Bits in Binary Representation
 * Count numbers in [left, right] whose popcount is prime.
 * 
 * Approach: Primes up to 32 are {2,3,5,7,11,13,17,19,23,29,31}. Use bitmask for O(1) check.
 * Time: O((right-left) * 32), Space: O(1)
 * 
 * Production Analogy: Filtering nodes by complexity tier based on active connections.
 */
public class Problem28_PrimeNumberOfSetBits {
    public static int countPrimeSetBits(int left, int right) {
        // Bitmask of primes: bit i set if i is prime
        int primes = 0b10100010100010101100; // bits 2,3,5,7,11,13,17,19 set
        int count = 0;
        for (int i = left; i <= right; i++) {
            if ((primes & (1 << Integer.bitCount(i))) != 0) count++;
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(countPrimeSetBits(6, 10)); // 4
        System.out.println(countPrimeSetBits(10, 15)); // 5
    }
}
