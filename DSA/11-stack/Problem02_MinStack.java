import java.util.*;

/**
 * Problem 2: Min Stack (LeetCode 155)
 * 
 * Design a stack that supports push, pop, top, and retrieving the minimum element in O(1).
 * 
 * Approach: Use two stacks - one for values and one tracking minimums.
 * Each push to min stack stores the current minimum at that level.
 * 
 * Time Complexity: O(1) for all operations
 * Space Complexity: O(n) for storing elements and mins
 * 
 * Production Analogy: Like a monitoring system that needs instant access to the
 * lowest latency/error-rate metric in a sliding window. Used in real-time dashboards
 * where you need min/max aggregations without re-scanning.
 */
public class Problem02_MinStack {

    static class MinStack {
        private Deque<Integer> stack = new ArrayDeque<>();
        private Deque<Integer> minStack = new ArrayDeque<>();

        public void push(int val) {
            stack.push(val);
            int min = minStack.isEmpty() ? val : Math.min(val, minStack.peek());
            minStack.push(min);
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

        MinStack ms2 = new MinStack();
        ms2.push(1);
        ms2.push(1);
        ms2.pop();
        System.out.println(ms2.getMin()); // 1
    }
}
