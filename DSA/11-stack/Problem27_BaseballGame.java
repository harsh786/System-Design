import java.util.*;

/**
 * Problem 27: Baseball Game (LeetCode 682)
 * 
 * Simulate baseball scoring with operations: number, +, D, C.
 * 
 * Approach: Stack simulation. Push scores, handle operations accordingly.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like an event-sourced system with undo (C), 
 * computed fields (+, D), and raw data inserts.
 */
public class Problem27_BaseballGame {

    public static int calPoints(String[] operations) {
        Deque<Integer> stack = new ArrayDeque<>();
        for (String op : operations) {
            switch (op) {
                case "+":
                    int top = stack.pop();
                    int newTop = top + stack.peek();
                    stack.push(top);
                    stack.push(newTop);
                    break;
                case "D": stack.push(2 * stack.peek()); break;
                case "C": stack.pop(); break;
                default: stack.push(Integer.parseInt(op));
            }
        }
        int sum = 0;
        for (int s : stack) sum += s;
        return sum;
    }

    public static void main(String[] args) {
        System.out.println(calPoints(new String[]{"5","2","C","D","+"})); // 30
        System.out.println(calPoints(new String[]{"5","-2","4","C","D","9","+","+"})); // 27
        System.out.println(calPoints(new String[]{"1","C"})); // 0
    }
}
