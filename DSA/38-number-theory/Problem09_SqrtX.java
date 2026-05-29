package numbertheory;

/**
 * Problem 9: Sqrt(x) (LeetCode 69)
 * 
 * Approach: Binary search for largest integer r where r*r <= x.
 * 
 * Time Complexity: O(log x)
 * Space Complexity: O(1)
 */
public class Problem09_SqrtX {
    
    public int mySqrt(int x) {
        if (x < 2) return x;
        long lo = 1, hi = x / 2;
        while (lo <= hi) {
            long mid = lo + (hi - lo) / 2;
            if (mid * mid == x) return (int) mid;
            if (mid * mid < x) lo = mid + 1;
            else hi = mid - 1;
        }
        return (int) hi;
    }
    
    public static void main(String[] args) {
        Problem09_SqrtX sol = new Problem09_SqrtX();
        System.out.println(sol.mySqrt(8));  // 2
        System.out.println(sol.mySqrt(16)); // 4
    }
}
