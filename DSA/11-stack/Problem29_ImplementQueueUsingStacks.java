import java.util.*;

/**
 * Problem 29: Implement Queue using Stacks (LeetCode 232)
 * 
 * Implement FIFO queue using only two LIFO stacks.
 * 
 * Approach: Two stacks - input and output. Push to input. For pop/peek,
 * if output empty, transfer all from input to output (reverses order = FIFO).
 * 
 * Time Complexity: O(1) amortized for all operations
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like message queue implementations that use internal stacks
 * for efficient batch processing while maintaining FIFO delivery order.
 */
public class Problem29_ImplementQueueUsingStacks {

    static class MyQueue {
        Deque<Integer> input = new ArrayDeque<>();
        Deque<Integer> output = new ArrayDeque<>();

        public void push(int x) { input.push(x); }

        public int pop() { peek(); return output.pop(); }

        public int peek() {
            if (output.isEmpty()) {
                while (!input.isEmpty()) output.push(input.pop());
            }
            return output.peek();
        }

        public boolean empty() { return input.isEmpty() && output.isEmpty(); }
    }

    public static void main(String[] args) {
        MyQueue q = new MyQueue();
        q.push(1);
        q.push(2);
        System.out.println(q.peek());  // 1
        System.out.println(q.pop());   // 1
        System.out.println(q.empty()); // false
        System.out.println(q.pop());   // 2
        System.out.println(q.empty()); // true
    }
}
