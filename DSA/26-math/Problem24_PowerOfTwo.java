/**
 * Problem 24: Power of Two
 * Determine if n is a power of two.
 *
 * Approach: n > 0 && (n & (n-1)) == 0. Power of two has single bit set.
 * Time Complexity: O(1)
 * Space Complexity: O(1)
 *
 * Production Analogy: Like validating memory allocation sizes (must be power of 2
 * for aligned memory access in hardware).
 */
public class Problem24_PowerOfTwo {

    public static boolean isPowerOfTwo(int n) {
        return n > 0 && (n & (n - 1)) == 0;
    }

    public static void main(String[] args) {
        System.out.println(isPowerOfTwo(1));   // true
        System.out.println(isPowerOfTwo(16));  // true
        System.out.println(isPowerOfTwo(3));   // false
        System.out.println(isPowerOfTwo(0));   // false
        System.out.println(isPowerOfTwo(Integer.MIN_VALUE)); // false
    }
}
