import java.util.*;

/**
 * Problem 30: Implement Stack using Queues (LeetCode 225)
 * 
 * Implement LIFO stack using only queues.
 * 
 * Approach: Single queue - on push, add element then rotate all previous elements
 * behind it. This makes the newest element always at front.
 * 
 * Time Complexity: O(n) push, O(1) pop/top
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like priority inversion in task scheduling where newest
 * high-priority tasks must be served first despite FIFO infrastructure.
 */
public class Problem30_ImplementStackUsingQueues {

    static class MyStack {
        Queue<Integer> queue = new LinkedList<>();

        public void push(int x) {
            queue.offer(x);
            int size = queue.size();
            for (int i = 0; i < size - 1; i++) {
                queue.offer(queue.poll());
            }
        }

        public int pop() { return queue.poll(); }
        public int top() { return queue.peek(); }
        public boolean empty() { return queue.isEmpty(); }
    }

    public static void main(String[] args) {
        MyStack s = new MyStack();
        s.push(1);
        s.push(2);
        System.out.println(s.top()); // 2
        System.out.println(s.pop()); // 2
        System.out.println(s.empty()); // false
    }
}
