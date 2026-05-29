package numbertheory;

/**
 * Problem 39: Valid Perfect Square (LeetCode 367)
 * 
 * Approach: Binary search or Newton's method.
 * 
 * Time Complexity: O(log n)
 * Space Complexity: O(1)
 */
public class Problem39_ValidPerfectSquare {
    
    public boolean isPerfectSquare(int num) {
        long lo = 1, hi = num;
        while (lo <= hi) {
            long mid = lo + (hi - lo) / 2;
            if (mid * mid == num) return true;
            if (mid * mid < num) lo = mid + 1;
            else hi = mid - 1;
        }
        return false;
    }
    
    public static void main(String[] args) {
        Problem39_ValidPerfectSquare sol = new Problem39_ValidPerfectSquare();
        System.out.println(sol.isPerfectSquare(16)); // true
        System.out.println(sol.isPerfectSquare(14)); // false
    }
}
