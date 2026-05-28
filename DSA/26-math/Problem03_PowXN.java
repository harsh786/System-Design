/**
 * Problem 3: Pow(x, n)
 * Implement pow(x, n) which calculates x raised to the power n.
 *
 * Approach: Fast exponentiation (binary exponentiation / exponentiation by squaring).
 * If n is even: x^n = (x^2)^(n/2). If n is odd: x^n = x * x^(n-1).
 * Time Complexity: O(log n)
 * Space Complexity: O(1) iterative
 *
 * Production Analogy: Like computing cryptographic keys in RSA where modular
 * exponentiation uses the same squaring technique for efficiency.
 */
public class Problem03_PowXN {

    public static double myPow(double x, int n) {
        long N = n;
        if (N < 0) {
            x = 1 / x;
            N = -N;
        }
        double result = 1.0;
        double current = x;
        while (N > 0) {
            if ((N & 1) == 1) result *= current;
            current *= current;
            N >>= 1;
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(myPow(2.0, 10));    // 1024.0
        System.out.println(myPow(2.1, 3));     // ~9.261
        System.out.println(myPow(2.0, -2));    // 0.25
        System.out.println(myPow(1.0, Integer.MIN_VALUE)); // 1.0
        System.out.println(myPow(2.0, 0));     // 1.0
        System.out.println(myPow(-2.0, 3));    // -8.0
        System.out.println(myPow(0.00001, 2147483647)); // 0.0
    }
}
