package numbertheory;

/**
 * Problem 16: Nth Magical Number (LeetCode 878)
 * 
 * Approach: Binary search. Count of magical numbers <= x is x/a + x/b - x/lcm(a,b).
 * 
 * Time Complexity: O(log(n * min(a,b)))
 * Space Complexity: O(1)
 */
public class Problem16_NthMagicalNumber {
    
    private static final int MOD = 1_000_000_007;
    
    public int nthMagicalNumber(int n, int a, int b) {
        long lcm = (long) a / gcd(a, b) * b;
        long lo = 1, hi = (long) n * Math.min(a, b);
        while (lo < hi) {
            long mid = lo + (hi - lo) / 2;
            if (mid / a + mid / b - mid / lcm >= n) hi = mid;
            else lo = mid + 1;
        }
        return (int) (lo % MOD);
    }
    
    private int gcd(int a, int b) { return b == 0 ? a : gcd(b, a % b); }
    
    public static void main(String[] args) {
        Problem16_NthMagicalNumber sol = new Problem16_NthMagicalNumber();
        System.out.println(sol.nthMagicalNumber(1, 2, 3)); // 2
        System.out.println(sol.nthMagicalNumber(4, 2, 3)); // 6
    }
}
