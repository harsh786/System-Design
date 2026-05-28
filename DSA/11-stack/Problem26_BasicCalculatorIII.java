import java.util.*;

/**
 * Problem 26: Basic Calculator III (LeetCode 772)
 * 
 * Evaluate expression with +, -, *, / and parentheses.
 * 
 * Approach: Recursive descent or stack-based. Use recursion for parentheses,
 * stack for operator precedence (* / processed immediately, + - stored).
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like a full expression evaluator in rule engines that
 * support nested conditions with different priority operators.
 */
public class Problem26_BasicCalculatorIII {

    static int i = 0;

    public static int calculate(String s) {
        i = 0;
        return eval(s);
    }

    private static int eval(String s) {
        Deque<Integer> stack = new ArrayDeque<>();
        int num = 0;
        char op = '+';
        while (i < s.length()) {
            char c = s.charAt(i);
            if (Character.isDigit(c)) {
                num = num * 10 + (c - '0');
            }
            if (c == '(') {
                i++;
                num = eval(s);
            }
            if ((!Character.isDigit(c) && c != ' ') || i == s.length() - 1) {
                switch (op) {
                    case '+': stack.push(num); break;
                    case '-': stack.push(-num); break;
                    case '*': stack.push(stack.pop() * num); break;
                    case '/': stack.push(stack.pop() / num); break;
                }
                op = c;
                num = 0;
                if (c == ')') break;
            }
            i++;
        }
        int result = 0;
        for (int n : stack) result += n;
        return result;
    }

    public static void main(String[] args) {
        System.out.println(calculate("1+1"));         // 2
        System.out.println(calculate("6-4/2"));       // 4
        System.out.println(calculate("2*(5+5*2)/3+(6/2+8)")); // 21
        System.out.println(calculate("(2+6*3+5-(3*14/7+2)*5)+3")); // -12
    }
}
