import java.util.*;

/**
 * Problem 9: Basic Calculator (LeetCode 224)
 * 
 * Implement a basic calculator to evaluate a string expression with +, -, (, ).
 * 
 * Approach: Use stack to handle parentheses. Track current result and sign.
 * When '(' encountered, push result and sign to stack. When ')' pop and combine.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like evaluating nested policy rules in an IAM system -
 * each parenthesis group is a policy scope that must be evaluated before
 * combining with the parent scope.
 */
public class Problem09_BasicCalculator {

    public static int calculate(String s) {
        Deque<Integer> stack = new ArrayDeque<>();
        int result = 0, num = 0, sign = 1;
        for (char c : s.toCharArray()) {
            if (Character.isDigit(c)) {
                num = num * 10 + (c - '0');
            } else if (c == '+') {
                result += sign * num;
                num = 0;
                sign = 1;
            } else if (c == '-') {
                result += sign * num;
                num = 0;
                sign = -1;
            } else if (c == '(') {
                stack.push(result);
                stack.push(sign);
                result = 0;
                sign = 1;
            } else if (c == ')') {
                result += sign * num;
                num = 0;
                result *= stack.pop(); // sign before parenthesis
                result += stack.pop(); // result before parenthesis
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
