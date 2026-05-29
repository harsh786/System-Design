/**
 * Problem 13: Ugly Number II
 * Find the nth ugly number (1, 2, 3, 4, 5, 6, 8, 9, 10, 12, ...).
 *
 * Approach: Three-pointer DP. Maintain pointers for multiples of 2, 3, 5.
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 *
 * Production Analogy: Like generating sorted merge streams from multiple
 * producers in event-driven architectures.
 */
public class Problem13_UglyNumberII {

    public static int nthUglyNumber(int n) {
        int[] ugly = new int[n];
        ugly[0] = 1;
        int p2 = 0, p3 = 0, p5 = 0;

        for (int i = 1; i < n; i++) {
            int next2 = ugly[p2] * 2, next3 = ugly[p3] * 3, next5 = ugly[p5] * 5;
            ugly[i] = Math.min(next2, Math.min(next3, next5));
            if (ugly[i] == next2) p2++;
            if (ugly[i] == next3) p3++;
            if (ugly[i] == next5) p5++;
        }
        return ugly[n - 1];
    }

    public static void main(String[] args) {
        System.out.println(nthUglyNumber(10));   // 12
        System.out.println(nthUglyNumber(1));    // 1
        System.out.println(nthUglyNumber(1690)); // 2123366400
    }
}
