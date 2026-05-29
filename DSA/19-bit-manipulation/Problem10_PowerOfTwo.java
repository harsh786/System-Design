/**
 * Problem 10: Power of Two
 * 
 * Approach: Power of 2 has exactly one set bit. n & (n-1) == 0 and n > 0.
 * Time: O(1), Space: O(1)
 * 
 * Production Analogy: Validating buffer sizes are powers of 2 for aligned memory allocation.
 */
public class Problem10_PowerOfTwo {
    public static boolean isPowerOfTwo(int n) {
        return n > 0 && (n & (n - 1)) == 0;
    }

    public static void main(String[] args) {
        System.out.println(isPowerOfTwo(1)); // true
        System.out.println(isPowerOfTwo(16)); // true
        System.out.println(isPowerOfTwo(3)); // false
        System.out.println(isPowerOfTwo(0)); // false
        System.out.println(isPowerOfTwo(-2147483648)); // false
    }
}
