package numbertheory;

/**
 * Problem 10: Pow(x, n) (LeetCode 50)
 * 
 * Approach: Fast exponentiation (binary exponentiation).
 * 
 * Time Complexity: O(log n)
 * Space Complexity: O(1)
 */
public class Problem10_PowXN {
    
    public double myPow(double x, int n) {
        long N = n;
        if (N < 0) { x = 1 / x; N = -N; }
        double result = 1;
        while (N > 0) {
            if ((N & 1) == 1) result *= x;
            x *= x;
            N >>= 1;
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem10_PowXN sol = new Problem10_PowXN();
        System.out.println(sol.myPow(2.0, 10));  // 1024.0
        System.out.println(sol.myPow(2.0, -2));  // 0.25
    }
}
