import java.util.*;

/**
 * Problem 2: Min Stack (LeetCode 155)
 * 
 * Design a stack that supports push, pop, top, and retrieving the minimum element in O(1).
 * 
 * Approach: Use two stacks - one for values, one tracking minimums at each level.
 * Time Complexity: O(1) for all operations
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like maintaining running statistics (min latency, min price)
 * in a streaming system where you can also "undo" the latest entry.
 */
public class Problem02_MinStack {

    static class MinStack {
        Deque<Integer> stack = new ArrayDeque<>();
        Deque<Integer> minStack = new ArrayDeque<>();

        public void push(int val) {
            stack.push(val);
            minStack.push(minStack.isEmpty() ? val : Math.min(val, minStack.peek()));
        }

        public void pop() {
            stack.pop();
            minStack.pop();
        }

        public int top() {
            return stack.peek();
        }

        public int getMin() {
            return minStack.peek();
        }
    }

    public static void main(String[] args) {
        MinStack ms = new MinStack();
        ms.push(-2);
        ms.push(0);
        ms.push(-3);
        System.out.println(ms.getMin()); // -3
        ms.pop();
        System.out.println(ms.top());    // 0
        System.out.println(ms.getMin()); // -2
    }
}
