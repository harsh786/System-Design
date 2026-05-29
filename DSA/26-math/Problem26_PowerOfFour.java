/**
 * Problem 26: Power of Four
 * Determine if n is a power of four.
 *
 * Approach: Power of 2 check + bit is at even position (mask 0x55555555).
 * Time Complexity: O(1)
 * Space Complexity: O(1)
 *
 * Production Analogy: Like validating quad-tree subdivision levels where each
 * level quadruples the cell count.
 */
public class Problem26_PowerOfFour {

    public static boolean isPowerOfFour(int n) {
        return n > 0 && (n & (n - 1)) == 0 && (n & 0x55555555) != 0;
    }

    public static void main(String[] args) {
        System.out.println(isPowerOfFour(16));  // true
        System.out.println(isPowerOfFour(5));   // false
        System.out.println(isPowerOfFour(1));   // true
        System.out.println(isPowerOfFour(8));   // false (power of 2, not 4)
    }
}
