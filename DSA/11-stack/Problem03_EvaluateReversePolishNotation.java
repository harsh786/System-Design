import java.util.*;

/**
 * Problem 3: Evaluate Reverse Polish Notation (LeetCode 150)
 * 
 * Evaluate the value of an arithmetic expression in Reverse Polish Notation.
 * 
 * Approach: Push numbers onto stack. On operator, pop two operands, compute, push result.
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: How compilers evaluate expressions after converting to postfix.
 * Also used in stack-based VMs (JVM bytecode evaluation).
 */
public class Problem03_EvaluateReversePolishNotation {

    public static int evalRPN(String[] tokens) {
        Deque<Integer> stack = new ArrayDeque<>();
        for (String t : tokens) {
            switch (t) {
                case "+": stack.push(stack.pop() + stack.pop()); break;
                case "-": int b = stack.pop(), a = stack.pop(); stack.push(a - b); break;
                case "*": stack.push(stack.pop() * stack.pop()); break;
                case "/": int d = stack.pop(), c = stack.pop(); stack.push(c / d); break;
                default: stack.push(Integer.parseInt(t));
            }
        }
        return stack.pop();
    }

    public static void main(String[] args) {
        System.out.println(evalRPN(new String[]{"2","1","+","3","*"})); // 9
        System.out.println(evalRPN(new String[]{"4","13","5","/","+"})); // 6
        System.out.println(evalRPN(new String[]{"10","6","9","3","+","-11","*","/","*","17","+","5","+"})); // 22
    }
}
