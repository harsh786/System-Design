/**
 * Problem: Min Queue Design
 * Two stacks or deque maintaining minimum at front.
 * Time: O(n) | Space: O(n)
 * Production Analogy: Priority queue for monitoring minimum response time in sliding window.
 */
import java.util.*;

public class Problem11_MinQueueDesign {
    private Deque<Integer> data = new ArrayDeque<>();
    private Deque<Integer> minDeque = new ArrayDeque<>();

    public void enqueue(int val) {
        data.offerLast(val);
        while (!minDeque.isEmpty() && minDeque.peekLast() > val) minDeque.pollLast();
        minDeque.offerLast(val);
    }

    public int dequeue() {
        int val = data.pollFirst();
        if (minDeque.peekFirst() == val) minDeque.pollFirst();
        return val;
    }

    public int getMin() { return minDeque.peekFirst(); }

    public static void main(String[] args) {
        Problem11_MinQueueDesign mq = new Problem11_MinQueueDesign();
        mq.enqueue(3); mq.enqueue(1); mq.enqueue(4);
        System.out.println("Min: " + mq.getMin()); // 1
        mq.dequeue();
        System.out.println("Min after dequeue: " + mq.getMin()); // 1
        mq.dequeue();
        System.out.println("Min after 2nd dequeue: " + mq.getMin()); // 4
    }
}
