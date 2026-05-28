import java.util.*;

/**
 * Problem 28: Basic Calculator (LeetCode 224)
 * 
 * Evaluate expression with +, -, (, ). 
 * Approach: Stack for sign tracking with parentheses. O(n) time, O(n) space.
 * 
 * Production Analogy: Like evaluating nested business rule expressions in a rules engine.
 */
public class Problem28_BasicCalculator {

    public static int calculate(String s) {
        Deque<Integer> stack = new ArrayDeque<>();
        int result = 0, num = 0, sign = 1;
        stack.push(1);
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (Character.isDigit(c)) {
                num = num * 10 + (c - '0');
            } else if (c == '+' || c == '-') {
                result += sign * num;
                num = 0;
                sign = stack.peek() * (c == '+' ? 1 : -1);
            } else if (c == '(') {
                stack.push(sign);
            } else if (c == ')') {
                stack.pop();
            }
        }
        return result + sign * num;
    }

    public static void main(String[] args) {
        System.out.println(calculate("1 + 1"));           // 2
        System.out.println(calculate(" 2-1 + 2 "));       // 3
        System.out.println(calculate("(1+(4+5+2)-3)+(6+8)")); // 23
        System.out.println(calculate("-(2+3)"));          // -5
    }
}
