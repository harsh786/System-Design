package numbertheory;

/**
 * Problem 23: Chinese Remainder Theorem
 * 
 * Approach: Given x ≡ r[i] (mod m[i]) for pairwise coprime m[i], find x mod M where M = product(m[i]).
 * 
 * Time Complexity: O(n * log(max_m))
 * Space Complexity: O(1)
 */
public class Problem23_ChineseRemainderTheorem {
    
    public long crt(long[] remainders, long[] moduli) {
        long M = 1;
        for (long m : moduli) M *= m;
        long result = 0;
        for (int i = 0; i < moduli.length; i++) {
            long Mi = M / moduli[i];
            long yi = modInverse(Mi, moduli[i]);
            result = (result + remainders[i] * Mi % M * yi) % M;
        }
        return (result + M) % M;
    }
    
    private long modInverse(long a, long m) {
        long[] res = extGcd(a % m + m, m);
        return (res[1] % m + m) % m;
    }
    
    private long[] extGcd(long a, long b) {
        if (b == 0) return new long[]{a, 1, 0};
        long[] r = extGcd(b, a % b);
        return new long[]{r[0], r[2], r[1] - (a / b) * r[2]};
    }
    
    public static void main(String[] args) {
        Problem23_ChineseRemainderTheorem sol = new Problem23_ChineseRemainderTheorem();
        // x ≡ 2 mod 3, x ≡ 3 mod 5, x ≡ 2 mod 7 => x = 23
        System.out.println(sol.crt(new long[]{2, 3, 2}, new long[]{3, 5, 7})); // 23
    }
}
