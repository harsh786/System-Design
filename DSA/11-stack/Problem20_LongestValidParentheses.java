import java.util.*;

/**
 * Problem 20: Longest Valid Parentheses (LeetCode 32)
 * 
 * Find length of longest valid (well-formed) parentheses substring.
 * 
 * Approach: Stack stores indices. Push -1 as base. For '(' push index.
 * For ')' pop; if stack empty push current index as new base, else calculate length.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like finding the longest uninterrupted valid session in
 * a stream of authentication tokens (open/close events).
 */
public class Problem20_LongestValidParentheses {

    public static int longestValidParentheses(String s) {
        Deque<Integer> stack = new ArrayDeque<>();
        stack.push(-1);
        int max = 0;
        for (int i = 0; i < s.length(); i++) {
            if (s.charAt(i) == '(') {
                stack.push(i);
            } else {
                stack.pop();
                if (stack.isEmpty()) {
                    stack.push(i);
                } else {
                    max = Math.max(max, i - stack.peek());
                }
            }
        }
        return max;
    }

    public static void main(String[] args) {
        System.out.println(longestValidParentheses("(()")); // 2
        System.out.println(longestValidParentheses(")()())")); // 4
        System.out.println(longestValidParentheses("")); // 0
        System.out.println(longestValidParentheses("()()")); // 4
    }
}
