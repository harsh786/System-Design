import java.util.*;

/**
 * Problem 21: Valid Parentheses (LeetCode 20)
 * 
 * Approach: Stack-based matching. O(n) time, O(n) space.
 * 
 * Production Analogy: Like validating JSON/XML nesting - each opener must have
 * a matching closer in the correct order.
 */
public class Problem21_ValidParentheses {

    public static boolean isValid(String s) {
        Deque<Character> stack = new ArrayDeque<>();
        for (char c : s.toCharArray()) {
            if (c == '(') stack.push(')');
            else if (c == '{') stack.push('}');
            else if (c == '[') stack.push(']');
            else if (stack.isEmpty() || stack.pop() != c) return false;
        }
        return stack.isEmpty();
    }

    public static void main(String[] args) {
        System.out.println(isValid("()"));     // true
        System.out.println(isValid("()[]{}"));  // true
        System.out.println(isValid("(]"));     // false
        System.out.println(isValid("([)]"));   // false
        System.out.println(isValid("{[]}"));   // true
        System.out.println(isValid(""));       // true
    }
}
