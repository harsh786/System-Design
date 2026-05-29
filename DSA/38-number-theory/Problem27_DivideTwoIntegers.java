package numbertheory;

/**
 * Problem 27: Divide Two Integers (LeetCode 29)
 * 
 * Approach: Subtract divisor shifted left (doubling) to simulate division via bit shifts.
 * 
 * Time Complexity: O(log^2 n)
 * Space Complexity: O(1)
 */
public class Problem27_DivideTwoIntegers {
    
    public int divide(int dividend, int divisor) {
        if (dividend == Integer.MIN_VALUE && divisor == -1) return Integer.MAX_VALUE;
        boolean neg = (dividend < 0) ^ (divisor < 0);
        long a = Math.abs((long) dividend), b = Math.abs((long) divisor);
        int result = 0;
        while (a >= b) {
            long temp = b;
            int shift = 0;
            while (a >= (temp << 1)) { temp <<= 1; shift++; }
            result += (1 << shift);
            a -= temp;
        }
        return neg ? -result : result;
    }
    
    public static void main(String[] args) {
        Problem27_DivideTwoIntegers sol = new Problem27_DivideTwoIntegers();
        System.out.println(sol.divide(10, 3));  // 3
        System.out.println(sol.divide(7, -2));  // -3
    }
}
