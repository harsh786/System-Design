/**
 * Problem 23: Valid Parenthesis String (LeetCode 678)
 *
 * Greedy Choice: Track min/max possible open count. '*' can be '(', ')' or empty.
 *
 * Time: O(n), Space: O(1)
 *
 * Production Analogy: Validating nested transaction brackets with wildcard recovery points.
 */
public class Problem23_ValidParenthesisString {
    
    public static boolean checkValidString(String s) {
        int lo = 0, hi = 0;
        for (char c : s.toCharArray()) {
            if (c == '(') { lo++; hi++; }
            else if (c == ')') { lo--; hi--; }
            else { lo--; hi++; }
            if (hi < 0) return false;
            lo = Math.max(lo, 0);
        }
        return lo == 0;
    }
    
    public static void main(String[] args) {
        System.out.println(checkValidString("()"));    // true
        System.out.println(checkValidString("(*)"));   // true
        System.out.println(checkValidString("(*))"));  // true
        System.out.println(checkValidString("(((*")); // false
    }
}
