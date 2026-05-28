/**
 * Problem 18: Monotone Increasing Digits (LeetCode 738)
 *
 * Greedy Choice: Find first decreasing pair from left, decrement and set rest to 9.
 *
 * Time: O(n), Space: O(n)
 *
 * Production Analogy: Finding largest non-decreasing threshold for tiered pricing.
 */
public class Problem18_MonotoneIncreasingDigits {
    
    public static int monotoneIncreasingDigits(int n) {
        char[] digits = String.valueOf(n).toCharArray();
        int mark = digits.length;
        for (int i = digits.length - 1; i > 0; i--) {
            if (digits[i] < digits[i-1]) {
                mark = i;
                digits[i-1]--;
            }
        }
        for (int i = mark; i < digits.length; i++) digits[i] = '9';
        return Integer.parseInt(new String(digits));
    }
    
    public static void main(String[] args) {
        System.out.println(monotoneIncreasingDigits(10));   // 9
        System.out.println(monotoneIncreasingDigits(1234)); // 1234
        System.out.println(monotoneIncreasingDigits(332));  // 299
        System.out.println(monotoneIncreasingDigits(1332)); // 1299
    }
}
