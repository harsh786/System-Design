import java.util.*;

/**
 * Problem 46: Implement Stack using Queues
 * 
 * API Contract:
 * - push(x): Push element
 * - pop(): Remove and return top
 * - top(): Return top element
 * - empty(): Check if empty
 * 
 * Complexity: push O(n), pop/top/empty O(1) (push-costly approach)
 * Data Structure: Single queue with rotation on push
 * 
 * Production Analogy: Adaptor pattern in software design,
 * protocol translation layers, interface compatibility wrappers
 */
public class Problem46_ImplementStackUsingQueues {

    static class MyStack {
        private Queue<Integer> queue;

        public MyStack() { queue = new LinkedList<>(); }

        public void push(int x) {
            queue.offer(x);
            // Rotate all previous elements to back
            for (int i = 0; i < queue.size() - 1; i++)
                queue.offer(queue.poll());
        }

        public int pop() { return queue.poll(); }
        public int top() { return queue.peek(); }
        public boolean empty() { return queue.isEmpty(); }
    }

    public static void main(String[] args) {
        MyStack s = new MyStack();
        s.push(1); s.push(2);
        assert s.top() == 2;
        assert s.pop() == 2;
        assert !s.empty();
        assert s.pop() == 1;
        assert s.empty();

        System.out.println("All tests passed!");
    }
}
