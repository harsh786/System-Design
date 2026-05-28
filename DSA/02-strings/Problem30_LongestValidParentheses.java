import java.util.*;

/**
 * Problem 30: Longest Valid Parentheses (LeetCode 32)
 * 
 * Approach: Stack stores indices. Push -1 as base. O(n) time, O(n) space.
 * 
 * Production Analogy: Like finding the longest correctly nested transaction sequence
 * in an event log.
 */
public class Problem30_LongestValidParentheses {

    public static int longestValidParentheses(String s) {
        Deque<Integer> stack = new ArrayDeque<>();
        stack.push(-1);
        int max = 0;
        for (int i = 0; i < s.length(); i++) {
            if (s.charAt(i) == '(') {
                stack.push(i);
            } else {
                stack.pop();
                if (stack.isEmpty()) stack.push(i);
                else max = Math.max(max, i - stack.peek());
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
