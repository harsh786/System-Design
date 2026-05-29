/**
 * Problem 25: Power of Three
 * Determine if n is a power of three.
 *
 * Approach: 3^19 = 1162261467 is largest power of 3 in int range. Check divisibility.
 * Time Complexity: O(1)
 * Space Complexity: O(1)
 *
 * Production Analogy: Like validating that ternary trie depths match expected powers.
 */
public class Problem25_PowerOfThree {

    public static boolean isPowerOfThree(int n) {
        return n > 0 && 1162261467 % n == 0;
    }

    public static void main(String[] args) {
        System.out.println(isPowerOfThree(27));  // true
        System.out.println(isPowerOfThree(0));   // false
        System.out.println(isPowerOfThree(9));   // true
        System.out.println(isPowerOfThree(45));  // false
    }
}
