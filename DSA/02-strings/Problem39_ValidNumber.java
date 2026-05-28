import java.util.*;

/**
 * Problem 39: Valid Number (LeetCode 65)
 * 
 * Approach: State machine or flag tracking. Track seen digits, dot, e/E.
 * O(n) time, O(1) space.
 * 
 * Production Analogy: Like input validation for a financial API - must handle all edge
 * cases of numeric formats (scientific notation, signed decimals).
 */
public class Problem39_ValidNumber {

    public static boolean isNumber(String s) {
        s = s.trim();
        boolean numSeen = false, dotSeen = false, eSeen = false;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (Character.isDigit(c)) {
                numSeen = true;
            } else if (c == '.') {
                if (dotSeen || eSeen) return false;
                dotSeen = true;
            } else if (c == 'e' || c == 'E') {
                if (eSeen || !numSeen) return false;
                eSeen = true;
                numSeen = false; // need digits after e
            } else if (c == '+' || c == '-') {
                if (i != 0 && s.charAt(i - 1) != 'e' && s.charAt(i - 1) != 'E') return false;
            } else {
                return false;
            }
        }
        return numSeen;
    }

    public static void main(String[] args) {
        String[] valid = {"2", "0089", "-0.1", "+3.14", "4.", "-.9", "2e10", "-90E3", "3e+7", "+6e-1", "53.5e93", "-123.456e789"};
        String[] invalid = {"abc", "1a", "1e", "e3", "99e2.5", "--6", "-+3", "95a54e53"};
        for (String v : valid) System.out.println(v + " -> " + isNumber(v));
        for (String inv : invalid) System.out.println(inv + " -> " + isNumber(inv));
    }
}
