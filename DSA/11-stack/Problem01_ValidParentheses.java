import java.util.*;

/**
 * Problem 1: Valid Parentheses (LeetCode 20)
 * 
 * Given a string containing just '(', ')', '{', '}', '[' and ']',
 * determine if the input string is valid.
 * 
 * Approach: Use a stack to push opening brackets and pop/match closing brackets.
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like validating XML/HTML tag nesting in a parser,
 * or ensuring every opened resource (file, connection) is properly closed.
 */
public class Problem01_ValidParentheses {
    
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
        System.out.println(isValid("()"));        // true
        System.out.println(isValid("()[]{}"));    // true
        System.out.println(isValid("(]"));        // false
        System.out.println(isValid("([)]"));      // false
        System.out.println(isValid("{[]}"));      // true
        System.out.println(isValid(""));          // true
        System.out.println(isValid("("));         // false
    }
}
