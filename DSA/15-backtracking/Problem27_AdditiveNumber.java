import java.util.*;

/**
 * Problem 27: Additive Number (LeetCode 306)
 * 
 * A string is additive if it can be split into numbers where each is sum of previous two.
 * 
 * Search Tree:
 * - Choose first two numbers (all possible splits), then validate chain
 * - Once first two are chosen, the rest is deterministic
 * 
 * Pruning Strategy:
 * - No leading zeros (except "0" itself)
 * - First number can be at most half the string length
 * - Use string addition for large numbers
 * 
 * Time Complexity: O(n^3) for choosing first two numbers, O(n) validation each
 * Space Complexity: O(n)
 * 
 * Production Analogy:
 * - Pattern detection in sequences: identifying Fibonacci-like patterns in time series data.
 */
public class Problem27_AdditiveNumber {

    public boolean isAdditiveNumber(String num) {
        int n = num.length();
        for (int i = 1; i <= n / 2; i++) {
            for (int j = i + 1; j < n; j++) {
                String s1 = num.substring(0, i);
                String s2 = num.substring(i, j);
                if (s1.length() > 1 && s1.charAt(0) == '0') break;
                if (s2.length() > 1 && s2.charAt(0) == '0') continue;
                if (isValid(num, j, s1, s2)) return true;
            }
        }
        return false;
    }

    private boolean isValid(String num, int start, String s1, String s2) {
        while (start < num.length()) {
            String sum = addStrings(s1, s2);
            if (!num.startsWith(sum, start)) return false;
            start += sum.length();
            s1 = s2;
            s2 = sum;
        }
        return true;
    }

    private String addStrings(String a, String b) {
        StringBuilder sb = new StringBuilder();
        int carry = 0, i = a.length() - 1, j = b.length() - 1;
        while (i >= 0 || j >= 0 || carry > 0) {
            int sum = carry;
            if (i >= 0) sum += a.charAt(i--) - '0';
            if (j >= 0) sum += b.charAt(j--) - '0';
            sb.append(sum % 10);
            carry = sum / 10;
        }
        return sb.reverse().toString();
    }

    public static void main(String[] args) {
        Problem27_AdditiveNumber sol = new Problem27_AdditiveNumber();

        System.out.println(sol.isAdditiveNumber("112358")); // true
        System.out.println(sol.isAdditiveNumber("199100199")); // true
        System.out.println(sol.isAdditiveNumber("1023")); // false
        System.out.println(sol.isAdditiveNumber("0235813")); // false
    }
}
