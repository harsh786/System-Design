/**
 * Problem 21: Divide Two Integers (without multiplication/division)
 * 
 * Approach: Use bit shifting. Double divisor until > dividend, subtract and accumulate.
 * Time: O(32) = O(1), Space: O(1)
 * 
 * Production Analogy: Resource allocation partitioning without expensive division hardware.
 */
public class Problem21_DivideTwoIntegers {
    public static int divide(int dividend, int divisor) {
        if (dividend == Integer.MIN_VALUE && divisor == -1) return Integer.MAX_VALUE;
        int sign = (dividend > 0) ^ (divisor > 0) ? -1 : 1;
        long a = Math.abs((long) dividend), b = Math.abs((long) divisor);
        int result = 0;
        for (int i = 31; i >= 0; i--) {
            if ((a >> i) >= b) {
                result += (1 << i);
                a -= (b << i);
            }
        }
        return sign * result;
    }

    public static void main(String[] args) {
        System.out.println(divide(10, 3)); // 3
        System.out.println(divide(7, -3)); // -2
        System.out.println(divide(Integer.MIN_VALUE, -1)); // Integer.MAX_VALUE
        System.out.println(divide(0, 1)); // 0
    }
}
