import java.util.*;

/**
 * Problem 47: Implement Queue using Stacks
 * 
 * API Contract:
 * - push(x): Enqueue
 * - pop(): Dequeue
 * - peek(): Front element
 * - empty(): Check if empty
 * 
 * Complexity: O(1) amortized for all operations
 * Data Structure: Two stacks - input stack + output stack (lazy transfer)
 * 
 * Production Analogy: Message queue built on stack-based storage,
 * amortized data structure design pattern
 */
public class Problem47_ImplementQueueUsingStacks {

    static class MyQueue {
        private Deque<Integer> in, out;

        public MyQueue() { in = new ArrayDeque<>(); out = new ArrayDeque<>(); }

        public void push(int x) { in.push(x); }

        public int pop() { transfer(); return out.pop(); }
        public int peek() { transfer(); return out.peek(); }
        public boolean empty() { return in.isEmpty() && out.isEmpty(); }

        private void transfer() {
            if (out.isEmpty()) while (!in.isEmpty()) out.push(in.pop());
        }
    }

    public static void main(String[] args) {
        MyQueue q = new MyQueue();
        q.push(1); q.push(2);
        assert q.peek() == 1;
        assert q.pop() == 1;
        assert !q.empty();
        q.push(3);
        assert q.pop() == 2;
        assert q.pop() == 3;
        assert q.empty();

        System.out.println("All tests passed!");
    }
}
