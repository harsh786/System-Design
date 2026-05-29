package numbertheory;

/**
 * Problem 20: Count Good Numbers (LeetCode 1922)
 * 
 * Approach: Even indices have 5 choices (0,2,4,6,8), odd indices have 4 choices (2,3,5,7).
 * Answer = 5^(ceil(n/2)) * 4^(floor(n/2)) mod 10^9+7. Use modular exponentiation.
 * 
 * Time Complexity: O(log n)
 * Space Complexity: O(1)
 */
public class Problem20_CountGoodNumbers {
    
    private static final long MOD = 1_000_000_007;
    
    public int countGoodNumbers(long n) {
        long evens = (n + 1) / 2, odds = n / 2;
        return (int) (modPow(5, evens) * modPow(4, odds) % MOD);
    }
    
    private long modPow(long base, long exp) {
        long result = 1; base %= MOD;
        while (exp > 0) {
            if ((exp & 1) == 1) result = result * base % MOD;
            base = base * base % MOD;
            exp >>= 1;
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem20_CountGoodNumbers sol = new Problem20_CountGoodNumbers();
        System.out.println(sol.countGoodNumbers(1));  // 5
        System.out.println(sol.countGoodNumbers(4));  // 400
        System.out.println(sol.countGoodNumbers(50)); // 564908303
    }
}
