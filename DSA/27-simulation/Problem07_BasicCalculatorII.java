/**
 * Problem: Basic Calculator II (LeetCode 227)
 * Approach: Stack-based simulation of operator precedence
 * Complexity: O(n) time, O(n) space
 * Production Analogy: Expression evaluation in query engines and rule processors
 */
import java.util.*;
public class Problem07_BasicCalculatorII {
    public int calculate(String s) {
        Deque<Integer> stack = new ArrayDeque<>();
        int num = 0; char op = '+';
        for (int i = 0; i <= s.length(); i++) {
            char c = i < s.length() ? s.charAt(i) : '+';
            if (Character.isDigit(c)) num = num*10 + (c-'0');
            else if (c != ' ') {
                if (op=='+') stack.push(num);
                else if (op=='-') stack.push(-num);
                else if (op=='*') stack.push(stack.pop()*num);
                else stack.push(stack.pop()/num);
                op = c; num = 0;
            }
        }
        int res = 0;
        for (int v : stack) res += v;
        return res;
    }
    public static void main(String[] args) {
        System.out.println(new Problem07_BasicCalculatorII().calculate("3+2*2")); // 7
    }
}
