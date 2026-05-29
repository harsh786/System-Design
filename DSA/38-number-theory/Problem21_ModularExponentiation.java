package numbertheory;

/**
 * Problem 21: Modular Exponentiation
 * 
 * Approach: Binary exponentiation: compute base^exp % mod efficiently.
 * 
 * Time Complexity: O(log exp)
 * Space Complexity: O(1)
 */
public class Problem21_ModularExponentiation {
    
    public long modPow(long base, long exp, long mod) {
        long result = 1;
        base %= mod;
        while (exp > 0) {
            if ((exp & 1) == 1) result = result * base % mod;
            base = base * base % mod;
            exp >>= 1;
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem21_ModularExponentiation sol = new Problem21_ModularExponentiation();
        System.out.println(sol.modPow(2, 10, 1000000007)); // 1024
        System.out.println(sol.modPow(3, 100, 1000000007)); // 981147432
    }
}
