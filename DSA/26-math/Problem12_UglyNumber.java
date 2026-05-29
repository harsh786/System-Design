/**
 * Problem 12: Ugly Number
 * Check if a number's only prime factors are 2, 3, and 5.
 *
 * Approach: Repeatedly divide by 2, 3, 5. If result is 1, it's ugly.
 * Time Complexity: O(log n)
 * Space Complexity: O(1)
 *
 * Production Analogy: Like validating that audio sample rates are products
 * of standard factors (44100 = 2^2 * 3^2 * 5^2 * 7^2... not ugly!).
 */
public class Problem12_UglyNumber {

    public static boolean isUgly(int n) {
        if (n <= 0) return false;
        while (n % 2 == 0) n /= 2;
        while (n % 3 == 0) n /= 3;
        while (n % 5 == 0) n /= 5;
        return n == 1;
    }

    public static void main(String[] args) {
        System.out.println(isUgly(6));   // true
        System.out.println(isUgly(1));   // true
        System.out.println(isUgly(14));  // false (7 is a factor)
        System.out.println(isUgly(0));   // false
        System.out.println(isUgly(-6));  // false
    }
}
