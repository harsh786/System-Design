import java.util.*;

/**
 * Problem 1: Valid Parentheses (LeetCode 20)
 * 
 * Given a string s containing just the characters '(', ')', '{', '}', '[' and ']',
 * determine if the input string is valid.
 * 
 * Approach: Use a stack to match opening brackets with closing brackets.
 * Push opening brackets onto stack, pop and compare for closing brackets.
 * 
 * Time Complexity: O(n) - single pass through string
 * Space Complexity: O(n) - stack can hold all opening brackets
 * 
 * Production Analogy: Like validating nested XML/HTML tags in a document parser,
 * or ensuring matching begin/end blocks in configuration files. Load balancers
 * use similar logic to validate HTTP request/response pairing.
 */
public class Problem01_ValidParentheses {
    
    public static boolean isValid(String s) {
        Deque<Character> stack = new ArrayDeque<>();
        for (char c : s.toCharArray()) {
            if (c == '(' || c == '{' || c == '[') {
                stack.push(c);
            } else {
                if (stack.isEmpty()) return false;
                char top = stack.pop();
                if (c == ')' && top != '(') return false;
                if (c == '}' && top != '{') return false;
                if (c == ']' && top != '[') return false;
            }
        }
        return stack.isEmpty();
    }

    public static void main(String[] args) {
        System.out.println(isValid("()"));        // true
        System.out.println(isValid("()[]{}"));    // true
        System.out.println(isValid("(]"));        // false
        System.out.println(isValid("([)]"));      // false
        System.out.println(isValid("{[]}"));      // true
        System.out.println(isValid(""));          // true (empty)
        System.out.println(isValid("("));         // false
        System.out.println(isValid("]"));         // false
    }
}
