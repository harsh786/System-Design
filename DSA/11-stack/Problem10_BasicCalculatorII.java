import java.util.*;

/**
 * Problem 10: Basic Calculator II (LeetCode 227)
 * 
 * Evaluate expression with +, -, *, / (no parentheses). Integer division truncates toward zero.
 * 
 * Approach: Stack stores intermediate results. Process * and / immediately (higher precedence),
 * push +/- values to stack, then sum everything at the end.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like query cost estimation in database optimizers that evaluate
 * higher-priority operations first before combining results.
 */
public class Problem10_BasicCalculatorII {

    public static int calculate(String s) {
        Deque<Integer> stack = new ArrayDeque<>();
        int num = 0;
        char op = '+';
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (Character.isDigit(c)) {
                num = num * 10 + (c - '0');
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
            }
        }
        int result = 0;
        for (int n : stack) result += n;
        return result;
    }

    public static void main(String[] args) {
        System.out.println(calculate("3+2*2"));     // 7
        System.out.println(calculate(" 3/2 "));     // 1
        System.out.println(calculate(" 3+5 / 2 ")); // 5
        System.out.println(calculate("0"));         // 0
        System.out.println(calculate("1-1+1"));     // 1
    }
}
