/**
 * Problem 47: Modular Exponentiation
 * Compute (base^exp) % mod efficiently.
 *
 * Approach: Binary exponentiation with modular arithmetic at each step.
 * Time Complexity: O(log exp)
 * Space Complexity: O(1)
 *
 * Production Analogy: Core operation in RSA encryption, Diffie-Hellman key exchange,
 * and digital signature algorithms.
 */
public class Problem47_ModularExponentiation {

    public static long modPow(long base, long exp, long mod) {
        if (mod == 1) return 0;
        long result = 1;
        base %= mod;
        while (exp > 0) {
            if ((exp & 1) == 1) {
                result = result * base % mod;
            }
            exp >>= 1;
            base = base * base % mod;
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(modPow(2, 10, 1000));        // 24
        System.out.println(modPow(3, 13, 7));           // 3
        System.out.println(modPow(2, 100, 1000000007)); // large
        System.out.println(modPow(5, 0, 7));            // 1
        System.out.println(modPow(0, 5, 7));            // 0
        System.out.println(modPow(2, 31, 1000000007));  // 2147483648 % MOD
    }
}
