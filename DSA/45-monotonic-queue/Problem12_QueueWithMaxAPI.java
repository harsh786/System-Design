/**
 * Problem: Queue with Max API
 * Auxiliary monotonic decreasing deque alongside main queue.
 * Time: O(n) | Space: O(n)
 * Production Analogy: Order queue showing highest-value pending order at any time.
 */
import java.util.*;

public class Problem12_QueueWithMaxAPI {
    private Deque<Integer> data = new ArrayDeque<>();
    private Deque<Integer> maxDeque = new ArrayDeque<>();

    public void enqueue(int val) {
        data.offerLast(val);
        while (!maxDeque.isEmpty() && maxDeque.peekLast() < val) maxDeque.pollLast();
        maxDeque.offerLast(val);
    }

    public int dequeue() {
        int val = data.pollFirst();
        if (maxDeque.peekFirst() == val) maxDeque.pollFirst();
        return val;
    }

    public int getMax() { return maxDeque.peekFirst(); }

    public static void main(String[] args) {
        Problem12_QueueWithMaxAPI q = new Problem12_QueueWithMaxAPI();
        q.enqueue(2); q.enqueue(5); q.enqueue(3);
        System.out.println("Max: " + q.getMax()); // 5
        q.dequeue(); q.dequeue();
        System.out.println("Max after 2 dequeues: " + q.getMax()); // 3
    }
}
