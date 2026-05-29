/**
 * Problem: Baseball Game (LeetCode 682)
 * Approach: Stack simulation of score operations
 * Complexity: O(n) time, O(n) space
 * Production Analogy: Event sourcing with computed aggregates
 */
import java.util.*;
public class Problem21_BaseballGame {
    public int calPoints(String[] operations) {
        Deque<Integer> stack = new ArrayDeque<>();
        for (String op : operations) {
            if (op.equals("+")) { int a=stack.pop(), b=stack.peek(); stack.push(a); stack.push(a+b); }
            else if (op.equals("D")) stack.push(stack.peek()*2);
            else if (op.equals("C")) stack.pop();
            else stack.push(Integer.parseInt(op));
        }
        int sum = 0; for (int v : stack) sum += v;
        return sum;
    }
    public static void main(String[] args) {
        System.out.println(new Problem21_BaseballGame().calPoints(new String[]{"5","2","C","D","+"})); // 30
    }
}
