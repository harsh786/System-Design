import java.util.*;

/**
 * Problem 13: String to Integer - atoi (LeetCode 8)
 * 
 * Implement atoi: skip whitespace, handle sign, read digits, clamp to 32-bit range.
 * O(n) time, O(1) space.
 * 
 * Production Analogy: Like parsing user input in a form field - must handle whitespace,
 * signs, overflow, and invalid characters gracefully.
 */
public class Problem13_StringToInteger {

    public static int myAtoi(String s) {
        int i = 0, n = s.length(), sign = 1;
        long result = 0;
        // Skip whitespace
        while (i < n && s.charAt(i) == ' ') i++;
        // Handle sign
        if (i < n && (s.charAt(i) == '+' || s.charAt(i) == '-')) {
            sign = s.charAt(i) == '-' ? -1 : 1;
            i++;
        }
        // Read digits
        while (i < n && Character.isDigit(s.charAt(i))) {
            result = result * 10 + (s.charAt(i) - '0');
            if (result * sign > Integer.MAX_VALUE) return Integer.MAX_VALUE;
            if (result * sign < Integer.MIN_VALUE) return Integer.MIN_VALUE;
            i++;
        }
        return (int)(result * sign);
    }

    public static void main(String[] args) {
        System.out.println(myAtoi("42"));             // 42
        System.out.println(myAtoi("   -42"));         // -42
        System.out.println(myAtoi("4193 with words"));// 4193
        System.out.println(myAtoi("words and 987"));  // 0
        System.out.println(myAtoi("-91283472332"));    // -2147483648
        System.out.println(myAtoi(""));               // 0
    }
}
