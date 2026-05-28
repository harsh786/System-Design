import java.util.*;

/**
 * Problem 3: Min Stack
 * 
 * API Contract:
 * - push(val): Push element onto stack
 * - pop(): Remove top element
 * - top(): Get top element
 * - getMin(): Retrieve minimum element in O(1)
 * 
 * Complexity: O(1) for all operations
 * Data Structure: Two stacks - main stack + min-tracking stack
 * 
 * Production Analogy: Monitoring systems tracking minimum latency in a sliding window,
 * order book tracking best bid/ask price
 */
public class Problem03_MinStack {

    static class MinStack {
        private Deque<Integer> stack;
        private Deque<Integer> minStack;

        public MinStack() {
            stack = new ArrayDeque<>();
            minStack = new ArrayDeque<>();
        }

        public void push(int val) {
            stack.push(val);
            if (minStack.isEmpty() || val <= minStack.peek()) {
                minStack.push(val);
            }
        }

        public void pop() {
            int val = stack.pop();
            if (val == minStack.peek()) {
                minStack.pop();
            }
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
        assert ms.getMin() == -3;
        ms.pop();
        assert ms.top() == 0;
        assert ms.getMin() == -2;

        // Edge: all same elements
        MinStack ms2 = new MinStack();
        ms2.push(1); ms2.push(1); ms2.push(1);
        ms2.pop();
        assert ms2.getMin() == 1;

        // Edge: decreasing sequence
        MinStack ms3 = new MinStack();
        ms3.push(3); ms3.push(2); ms3.push(1);
        assert ms3.getMin() == 1;
        ms3.pop();
        assert ms3.getMin() == 2;

        System.out.println("All tests passed!");
    }
}
