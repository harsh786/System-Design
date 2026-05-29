/**
 * Problem 38: Nth Magical Number
 * A number is magical if divisible by a or b. Find nth magical number (mod 10^9+7).
 *
 * Approach: Binary search. Count of magical numbers <= x is x/a + x/b - x/lcm(a,b).
 * Time Complexity: O(log(N * min(a,b)))
 * Space Complexity: O(1)
 *
 * Production Analogy: Like computing the nth event in a system with multiple
 * periodic triggers (cron jobs with different intervals).
 */
public class Problem38_NthMagicalNumber {

    public static int nthMagicalNumber(int n, int a, int b) {
        long MOD = 1_000_000_007;
        long lcm = (long) a / gcd(a, b) * b;
        long lo = 1, hi = (long) n * Math.min(a, b);

        while (lo < hi) {
            long mid = lo + (hi - lo) / 2;
            long count = mid / a + mid / b - mid / lcm;
            if (count < n) lo = mid + 1;
            else hi = mid;
        }
        return (int) (lo % MOD);
    }

    private static int gcd(int a, int b) {
        return b == 0 ? a : gcd(b, a % b);
    }

    public static void main(String[] args) {
        System.out.println(nthMagicalNumber(1, 2, 3));  // 2
        System.out.println(nthMagicalNumber(4, 2, 3));  // 6
        System.out.println(nthMagicalNumber(5, 2, 4));  // 10
        System.out.println(nthMagicalNumber(1000000000, 40000, 40000)); // large
    }
}
