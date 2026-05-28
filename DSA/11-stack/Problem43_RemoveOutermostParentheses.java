import java.util.*;

/**
 * Problem 43: Remove Outermost Parentheses (LeetCode 1021)
 * 
 * Remove outermost parentheses of every primitive decomposition.
 * 
 * Approach: Track depth. Only append when depth > 0 for '(' or depth > 1 for after increment.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like stripping wrapper/envelope elements from nested message
 * formats (e.g., removing SOAP envelopes to get payload).
 */
public class Problem43_RemoveOutermostParentheses {

    public static String removeOuterParentheses(String s) {
        StringBuilder sb = new StringBuilder();
        int depth = 0;
        for (char c : s.toCharArray()) {
            if (c == '(') { if (depth++ > 0) sb.append(c); }
            else { if (--depth > 0) sb.append(c); }
        }
        return sb.toString();
    }

    public static void main(String[] args) {
        System.out.println(removeOuterParentheses("(()())(())")); // ()()()
        System.out.println(removeOuterParentheses("(()())(())(()(()))")); // ()()()()(())
        System.out.println(removeOuterParentheses("()()"));       // (empty)
    }
}
