/**
 * Problem 15: Pow(x, n) - LeetCode 50
 * 
 * D&C Approach (Binary Exponentiation):
 * - DIVIDE: x^n = x^(n/2) * x^(n/2) if n even, x * x^(n-1) if n odd
 * - CONQUER: Compute x^(n/2) recursively once
 * - COMBINE: Square the result (multiply for odd)
 * 
 * Recurrence: T(n) = T(n/2) + O(1)
 * Time: O(log n), Space: O(log n) or O(1) iterative
 * 
 * Production Analogy:
 * - RSA encryption (modular exponentiation)
 * - Matrix exponentiation for Fibonacci in O(log n)
 * - Fast computation of large powers in cryptography
 */
public class Problem15_PowXN {

    public static double myPow(double x, int n) {
        long N = n; // Handle Integer.MIN_VALUE overflow
        if (N < 0) { x = 1 / x; N = -N; }
        return fastPow(x, N);
    }

    private static double fastPow(double x, long n) {
        if (n == 0) return 1.0;
        double half = fastPow(x, n / 2);
        if (n % 2 == 0) return half * half;
        else return half * half * x;
    }

    // Iterative version - O(1) space
    public static double myPowIterative(double x, int n) {
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
        System.out.println(myPowIterative(2.0, 10)); // 1024.0
    }
}
