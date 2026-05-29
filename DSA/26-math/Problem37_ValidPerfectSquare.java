/**
 * Problem 37: Valid Perfect Square
 * Determine if num is a perfect square without using sqrt.
 *
 * Approach: Binary search for x where x*x == num.
 * Time Complexity: O(log n)
 * Space Complexity: O(1)
 *
 * Production Analogy: Like validating array dimensions in matrix operations
 * where dimensions must be perfect squares for square matrices.
 */
public class Problem37_ValidPerfectSquare {

    public static boolean isPerfectSquare(int num) {
        long lo = 1, hi = num;
        while (lo <= hi) {
            long mid = lo + (hi - lo) / 2;
            long sq = mid * mid;
            if (sq == num) return true;
            else if (sq < num) lo = mid + 1;
            else hi = mid - 1;
        }
        return false;
    }

    public static void main(String[] args) {
        System.out.println(isPerfectSquare(16));  // true
        System.out.println(isPerfectSquare(14));  // false
        System.out.println(isPerfectSquare(1));   // true
        System.out.println(isPerfectSquare(2147483647)); // false
    }
}
