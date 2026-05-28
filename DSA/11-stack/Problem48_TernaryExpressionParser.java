import java.util.*;

/**
 * Problem 48: Ternary Expression Parser (LeetCode 439)
 * 
 * Parse ternary expression "T?2:3" -> "2", "F?1:T?4:5" -> "4".
 * 
 * Approach: Process from right to left using stack. When '?' found, pop two values
 * and choose based on condition character before '?'.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like evaluating feature flag conditions in cascading configuration
 * systems where flags can depend on other flags.
 */
public class Problem48_TernaryExpressionParser {

    public static String parseTernary(String expression) {
        Deque<Character> stack = new ArrayDeque<>();
        for (int i = expression.length() - 1; i >= 0; i--) {
            char c = expression.charAt(i);
            if (!stack.isEmpty() && stack.peek() == '?') {
                stack.pop(); // remove '?'
                char first = stack.pop();
                stack.pop(); // remove ':'
                char second = stack.pop();
                stack.push(c == 'T' ? first : second);
            } else {
                stack.push(c);
            }
        }
        return String.valueOf(stack.pop());
    }

    public static void main(String[] args) {
        System.out.println(parseTernary("T?2:3"));       // 2
        System.out.println(parseTernary("F?1:T?4:5"));   // 4
        System.out.println(parseTernary("T?T?F:5:3"));   // F
    }
}
