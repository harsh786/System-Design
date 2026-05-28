import java.util.*;

/**
 * Problem 35: Parsing A Boolean Expression (LeetCode 1106)
 * 
 * Evaluate boolean expression: t, f, !(expr), &(expr1,expr2,...), |(expr1,expr2,...)
 * 
 * Approach: Stack-based. Push characters. On ')', collect all values until '(',
 * then apply the operator before '('.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like evaluating complex ACL/IAM policy rules with AND/OR/NOT
 * combinators at multiple nesting levels.
 */
public class Problem35_ParsingBooleanExpression {

    public static boolean parseBoolExpr(String expression) {
        Deque<Character> stack = new ArrayDeque<>();
        for (char c : expression.toCharArray()) {
            if (c == ',') continue;
            if (c != ')') {
                stack.push(c);
            } else {
                boolean hasTrue = false, hasFalse = false;
                while (stack.peek() != '(') {
                    char val = stack.pop();
                    if (val == 't') hasTrue = true;
                    else hasFalse = true;
                }
                stack.pop(); // remove '('
                char op = stack.pop(); // operator
                if (op == '!') stack.push(hasTrue ? 'f' : 't');
                else if (op == '&') stack.push(hasFalse ? 'f' : 't');
                else stack.push(hasTrue ? 't' : 'f');
            }
        }
        return stack.pop() == 't';
    }

    public static void main(String[] args) {
        System.out.println(parseBoolExpr("!(f)"));        // true
        System.out.println(parseBoolExpr("|(f,t)"));      // true
        System.out.println(parseBoolExpr("&(t,f)"));      // false
        System.out.println(parseBoolExpr("|(&(t,f,t),!(t))")); // false
    }
}
