package numbertheory;

import java.util.Random;

/**
 * Problem 50: Miller-Rabin Primality Test
 * 
 * Approach: Probabilistic primality test. Write n-1 = 2^r * d.
 * For witness a, check if a^d ≡ 1 (mod n) or a^(2^i * d) ≡ -1 (mod n) for some i.
 * Deterministic for n < 3.3*10^24 with specific witnesses.
 * 
 * Time Complexity: O(k * log^2 n) where k = number of witnesses
 * Space Complexity: O(1)
 */
public class Problem50_MillerRabinPrimalityTest {
    
    public boolean isPrime(long n) {
        if (n < 2) return false;
        if (n < 4) return true;
        if (n % 2 == 0 || n % 3 == 0) return false;
        // Deterministic witnesses for n < 3,317,044,064,679,887,385,961,981
        long[] witnesses = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37};
        long d = n - 1;
        int r = 0;
        while (d % 2 == 0) { d /= 2; r++; }
        for (long a : witnesses) {
            if (a >= n) continue;
            if (!millerTest(a, d, n, r)) return false;
        }
        return true;
    }
    
    private boolean millerTest(long a, long d, long n, int r) {
        long x = modPow(a, d, n);
        if (x == 1 || x == n - 1) return true;
        for (int i = 0; i < r - 1; i++) {
            x = mulMod(x, x, n);
            if (x == n - 1) return true;
        }
        return false;
    }
    
    private long modPow(long base, long exp, long mod) {
        long result = 1;
        base %= mod;
        while (exp > 0) {
            if ((exp & 1) == 1) result = mulMod(result, base, mod);
            base = mulMod(base, base, mod);
            exp >>= 1;
        }
        return result;
    }
    
    // Handles overflow for large numbers using Math.multiplyHigh or BigInteger-like approach
    private long mulMod(long a, long b, long mod) {
        return java.math.BigInteger.valueOf(a).multiply(java.math.BigInteger.valueOf(b)).mod(java.math.BigInteger.valueOf(mod)).longValue();
    }
    
    public static void main(String[] args) {
        Problem50_MillerRabinPrimalityTest sol = new Problem50_MillerRabinPrimalityTest();
        System.out.println(sol.isPrime(2));          // true
        System.out.println(sol.isPrime(997));        // true
        System.out.println(sol.isPrime(1000000007)); // true
        System.out.println(sol.isPrime(1000000009)); // true
        System.out.println(sol.isPrime(4));          // false
        System.out.println(sol.isPrime(561));        // false (Carmichael number)
    }
}
