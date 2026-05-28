/**
 * Problem 29: Valid Perfect Square
 * 
 * Determine if num is a perfect square without using sqrt.
 * 
 * Time: O(log n), Space: O(1)
 * 
 * Production Analogy: Validating if a resource pool can be evenly distributed
 * in a square grid topology.
 */
public class Problem29_ValidPerfectSquare {
    public static boolean isPerfectSquare(int num) {
        long lo = 1, hi = num;
        while (lo <= hi) {
            long mid = lo + (hi - lo) / 2;
            if (mid * mid == num) return true;
            else if (mid * mid < num) lo = mid + 1;
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
