/**
 * Problem 5: Divide Two Integers
 * Divide without multiplication, division, or mod. Return truncated quotient.
 *
 * Approach: Use bit shifting. Double the divisor until it exceeds dividend,
 * then subtract and accumulate the quotient.
 * Time Complexity: O(log^2 n)
 * Space Complexity: O(1)
 *
 * Production Analogy: Like implementing division in hardware ALU using shift-subtract.
 */
public class Problem05_DivideTwoIntegers {

    public static int divide(int dividend, int divisor) {
        if (dividend == Integer.MIN_VALUE && divisor == -1)
            return Integer.MAX_VALUE; // overflow case

        boolean negative = (dividend < 0) ^ (divisor < 0);
        long a = Math.abs((long) dividend);
        long b = Math.abs((long) divisor);
        int result = 0;

        while (a >= b) {
            long temp = b;
            int shift = 0;
            while (a >= (temp << 1)) {
                temp <<= 1;
                shift++;
            }
            a -= temp;
            result += (1 << shift);
        }
        return negative ? -result : result;
    }

    public static void main(String[] args) {
        System.out.println(divide(10, 3));        // 3
        System.out.println(divide(7, -3));        // -2
        System.out.println(divide(Integer.MIN_VALUE, -1)); // 2147483647
        System.out.println(divide(Integer.MIN_VALUE, 1));  // -2147483648
        System.out.println(divide(0, 1));         // 0
        System.out.println(divide(1, 1));         // 1
    }
}
