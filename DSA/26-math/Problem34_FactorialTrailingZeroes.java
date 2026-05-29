/**
 * Problem 34: Factorial Trailing Zeroes
 * Count trailing zeroes in n!.
 *
 * Approach: Count factors of 5 in n! (there are always more 2s than 5s).
 * n/5 + n/25 + n/125 + ...
 * Time Complexity: O(log5(n))
 * Space Complexity: O(1)
 *
 * Production Analogy: Like estimating precision loss in floating-point
 * multiplication chains.
 */
public class Problem34_FactorialTrailingZeroes {

    public static int trailingZeroes(int n) {
        int count = 0;
        while (n >= 5) {
            n /= 5;
            count += n;
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(trailingZeroes(3));    // 0
        System.out.println(trailingZeroes(5));    // 1
        System.out.println(trailingZeroes(25));   // 6
        System.out.println(trailingZeroes(100));  // 24
    }
}
