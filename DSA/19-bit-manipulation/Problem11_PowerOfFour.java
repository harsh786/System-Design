/**
 * Problem 11: Power of Four
 * 
 * Approach: Must be power of 2 AND set bit at even position (mask 0x55555555).
 * Time: O(1), Space: O(1)
 * 
 * Production Analogy: Validating quad-tree node capacities.
 */
public class Problem11_PowerOfFour {
    public static boolean isPowerOfFour(int n) {
        // Power of 2 check + bit at even position (0-indexed)
        return n > 0 && (n & (n - 1)) == 0 && (n & 0x55555555) != 0;
    }

    public static void main(String[] args) {
        System.out.println(isPowerOfFour(16)); // true
        System.out.println(isPowerOfFour(5)); // false
        System.out.println(isPowerOfFour(1)); // true
        System.out.println(isPowerOfFour(8)); // false (power of 2, not 4)
    }
}
