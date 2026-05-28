/**
 * Problem 14: Sqrt(x)
 * 
 * Compute floor(sqrt(x)) without using built-in sqrt.
 * 
 * Approach: Binary search on [0, x]. Find largest mid where mid*mid <= x.
 * 
 * Time: O(log x), Space: O(1)
 * 
 * Production Analogy: Estimating resource allocation where cost grows
 * quadratically — finding the maximum units within budget.
 */
public class Problem14_Sqrt {
    public static int mySqrt(int x) {
        if (x < 2) return x;
        long lo = 1, hi = x / 2;
        while (lo <= hi) {
            long mid = lo + (hi - lo) / 2;
            if (mid * mid == x) return (int) mid;
            else if (mid * mid < x) lo = mid + 1;
            else hi = mid - 1;
        }
        return (int) hi;
    }

    public static void main(String[] args) {
        System.out.println(mySqrt(4));          // 2
        System.out.println(mySqrt(8));          // 2
        System.out.println(mySqrt(0));          // 0
        System.out.println(mySqrt(1));          // 1
        System.out.println(mySqrt(2147395600)); // 46340
    }
}
