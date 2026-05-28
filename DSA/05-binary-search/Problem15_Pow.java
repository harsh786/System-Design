/**
 * Problem 15: Pow(x, n)
 * 
 * Implement pow(x, n) using binary exponentiation.
 * 
 * Approach: Fast power — if n is even, x^n = (x^(n/2))^2; if odd, multiply extra x.
 * 
 * Time: O(log n), Space: O(1) iterative
 * 
 * Production Analogy: Efficient repeated computation (like compound interest
 * calculation) using squaring to reduce O(n) multiplications to O(log n).
 */
public class Problem15_Pow {
    public static double myPow(double x, int n) {
        long N = n;
        if (N < 0) { x = 1 / x; N = -N; }
        double result = 1.0;
        while (N > 0) {
            if ((N & 1) == 1) result *= x;
            x *= x;
            N >>= 1;
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(myPow(2.0, 10));    // 1024.0
        System.out.println(myPow(2.1, 3));     // 9.261
        System.out.println(myPow(2.0, -2));    // 0.25
        System.out.println(myPow(1.0, Integer.MIN_VALUE)); // 1.0
        System.out.println(myPow(2.0, 0));     // 1.0
    }
}
