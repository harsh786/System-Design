/**
 * Problem 39: Super Pow
 * Calculate a^b mod 1337 where b is represented as an array.
 *
 * Approach: a^1234 = (a^123)^10 * a^4. Process digit by digit.
 * Time Complexity: O(n) where n is length of b
 * Space Complexity: O(1)
 *
 * Production Analogy: Like computing modular powers in public key cryptography
 * where exponents exceed machine word size.
 */
public class Problem39_SuperPow {
    private static final int MOD = 1337;

    public static int superPow(int a, int[] b) {
        int result = 1;
        a %= MOD;
        for (int digit : b) {
            result = power(result, 10) * power(a, digit) % MOD;
        }
        return result;
    }

    private static int power(int base, int exp) {
        base %= MOD;
        int result = 1;
        for (int i = 0; i < exp; i++) {
            result = result * base % MOD;
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(superPow(2, new int[]{3}));       // 8
        System.out.println(superPow(2, new int[]{1,0}));     // 1024
        System.out.println(superPow(1, new int[]{4,3,3,8,5,2})); // 1
        System.out.println(superPow(2147483647, new int[]{2,0,0})); // result mod 1337
    }
}
