package numbertheory;

/**
 * Problem 40: Super Pow (LeetCode 372)
 * 
 * Approach: a^[1,5,6,4] = (a^[1,5,6])^10 * a^4. Recursive with mod.
 * 
 * Time Complexity: O(n) where n = digits in b
 * Space Complexity: O(n)
 */
public class Problem40_SuperPow {
    
    private static final int MOD = 1337;
    
    public int superPow(int a, int[] b) {
        return helper(a % MOD, b, b.length - 1);
    }
    
    private int helper(int a, int[] b, int idx) {
        if (idx < 0) return 1;
        return (int) ((long) powMod(helper(a, b, idx - 1), 10) * powMod(a, b[idx]) % MOD);
    }
    
    private int powMod(int base, int exp) {
        base %= MOD;
        int result = 1;
        while (exp > 0) {
            if ((exp & 1) == 1) result = (int) ((long) result * base % MOD);
            base = (int) ((long) base * base % MOD);
            exp >>= 1;
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem40_SuperPow sol = new Problem40_SuperPow();
        System.out.println(sol.superPow(2, new int[]{1, 0})); // 1024 % 1337 = 1024
        System.out.println(sol.superPow(2, new int[]{3}));    // 8
    }
}
