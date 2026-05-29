/**
 * Problem 48: Chinese Remainder Theorem
 * Find x such that x ≡ r[i] (mod m[i]) for all i, where m[i] are pairwise coprime.
 *
 * Approach: CRT construction: x = sum(r[i] * M[i] * inv(M[i], m[i])) mod M
 * where M = product of all m[i], M[i] = M / m[i].
 * Time Complexity: O(n * log(max_m)) for extended GCD
 * Space Complexity: O(1)
 *
 * Production Analogy: Like secret sharing (Shamir's) or parallel computation
 * where partial results from independent moduli are combined.
 */
public class Problem48_ChineseRemainderTheorem {

    public static long chineseRemainder(long[] remainders, long[] moduli) {
        long M = 1;
        for (long m : moduli) M *= m;

        long result = 0;
        for (int i = 0; i < moduli.length; i++) {
            long Mi = M / moduli[i];
            long yi = modInverse(Mi, moduli[i]);
            result = (result + remainders[i] * Mi % M * yi % M) % M;
        }
        return (result + M) % M;
    }

    // Extended Euclidean to find modular inverse
    private static long modInverse(long a, long m) {
        long[] res = extGcd(a % m, m);
        return (res[1] % m + m) % m;
    }

    private static long[] extGcd(long a, long b) {
        if (a == 0) return new long[]{b, 0, 1};
        long[] r = extGcd(b % a, a);
        return new long[]{r[0], r[2] - (b / a) * r[1], r[1]};
    }

    public static void main(String[] args) {
        // x ≡ 2 (mod 3), x ≡ 3 (mod 5), x ≡ 2 (mod 7) => x = 23
        System.out.println(chineseRemainder(new long[]{2,3,2}, new long[]{3,5,7})); // 23

        // x ≡ 1 (mod 2), x ≡ 2 (mod 3), x ≡ 3 (mod 5) => x = 23
        System.out.println(chineseRemainder(new long[]{1,2,3}, new long[]{2,3,5})); // 23
    }
}
