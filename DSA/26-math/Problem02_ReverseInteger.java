/**
 * Problem 2: Reverse Integer
 * Reverse digits of a 32-bit signed integer. Return 0 if overflow.
 *
 * Approach: Pop digits from end, push to result, check overflow before multiply.
 * Time Complexity: O(log10(n))
 * Space Complexity: O(1)
 *
 * Production Analogy: Like reversing byte order (endianness conversion) with
 * overflow guards in network protocol handling.
 */
public class Problem02_ReverseInteger {

    public static int reverse(int x) {
        int result = 0;
        while (x != 0) {
            int digit = x % 10;
            x /= 10;
            // Check overflow before it happens
            if (result > Integer.MAX_VALUE / 10 || (result == Integer.MAX_VALUE / 10 && digit > 7))
                return 0;
            if (result < Integer.MIN_VALUE / 10 || (result == Integer.MIN_VALUE / 10 && digit < -8))
                return 0;
            result = result * 10 + digit;
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(reverse(123));        // 321
        System.out.println(reverse(-123));       // -321
        System.out.println(reverse(120));        // 21
        System.out.println(reverse(0));          // 0
        System.out.println(reverse(1534236469)); // 0 (overflow)
        System.out.println(reverse(Integer.MAX_VALUE)); // 0
        System.out.println(reverse(Integer.MIN_VALUE)); // 0
    }
}
