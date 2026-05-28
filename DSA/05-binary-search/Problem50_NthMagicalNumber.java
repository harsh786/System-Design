/**
 * Problem 50: Nth Magical Number
 * 
 * A number is magical if divisible by a or b. Find the nth magical number.
 * 
 * Approach: Binary search on answer. Count of magical numbers <= x is:
 * x/a + x/b - x/lcm(a,b). Find smallest x with count >= n.
 * 
 * Time: O(log(n * min(a,b))), Space: O(1)
 * 
 * Production Analogy: Finding the nth event in a system with two periodic
 * schedulers running at different intervals (cron union).
 */
public class Problem50_NthMagicalNumber {
    private static final int MOD = 1_000_000_007;

    public static int nthMagicalNumber(int n, int a, int b) {
        long lcm = (long) a / gcd(a, b) * b;
        long lo = 1, hi = (long) n * Math.min(a, b);
        
        while (lo < hi) {
            long mid = lo + (hi - lo) / 2;
            long count = mid / a + mid / b - mid / lcm;
            if (count >= n) hi = mid;
            else lo = mid + 1;
        }
        return (int) (lo % MOD);
    }

    private static int gcd(int a, int b) { return b == 0 ? a : gcd(b, a % b); }

    public static void main(String[] args) {
        System.out.println(nthMagicalNumber(1, 2, 3));    // 2
        System.out.println(nthMagicalNumber(4, 2, 3));    // 6
        System.out.println(nthMagicalNumber(5, 2, 4));    // 10
        System.out.println(nthMagicalNumber(3, 6, 4));    // 8
        System.out.println(nthMagicalNumber(1000000000, 40000, 40000)); // 999720007
    }
}
