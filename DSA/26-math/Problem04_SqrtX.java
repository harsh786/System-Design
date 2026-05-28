/**
 * Problem 4: Sqrt(x)
 * Compute integer square root (floor) without using built-in sqrt.
 *
 * Approach: Binary search on answer space [0, x]. mid*mid <= x means go right.
 * Time Complexity: O(log x)
 * Space Complexity: O(1)
 *
 * Production Analogy: Like binary search in sorted index lookups in databases -
 * narrowing the search space logarithmically.
 */
public class Problem04_SqrtX {

    public static int mySqrt(int x) {
        if (x < 2) return x;
        long lo = 1, hi = x / 2;
        while (lo <= hi) {
            long mid = lo + (hi - lo) / 2;
            long sq = mid * mid;
            if (sq == x) return (int) mid;
            else if (sq < x) lo = mid + 1;
            else hi = mid - 1;
        }
        return (int) hi;
    }

    public static void main(String[] args) {
        System.out.println(mySqrt(4));          // 2
        System.out.println(mySqrt(8));          // 2
        System.out.println(mySqrt(0));          // 0
        System.out.println(mySqrt(1));          // 1
        System.out.println(mySqrt(2147395599)); // 46339
        System.out.println(mySqrt(Integer.MAX_VALUE)); // 46340
    }
}
