/**
 * Problem: Thread-safe Queue
 * Queue with synchronized enqueue/dequeue.
 * 
 * Approach: See implementation below.
 * Time Complexity: O(1) per operation
 * Space Complexity: O(n)
 * 
 * Production Analogy: Task queue in worker pool pattern.
 */
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem17_ThreadSafeQueue {
    private final LinkedList<Integer> list = new LinkedList<>();

    public synchronized void enqueue(int val) { list.addLast(val); notifyAll(); }

    public synchronized int dequeue() throws InterruptedException {
        while (list.isEmpty()) wait();
        return list.removeFirst();
    }

    public synchronized int size() { return list.size(); }

    public static void main(String[] args) throws InterruptedException {
        Problem17_ThreadSafeQueue q = new Problem17_ThreadSafeQueue();
        new Thread(() -> { for (int i = 0; i < 5; i++) q.enqueue(i); }).start();
        Thread.sleep(100);
        new Thread(() -> { try { for (int i = 0; i < 5; i++) System.out.println("Dequeued: " + q.dequeue()); } catch (InterruptedException e) {} }).start();
        Thread.sleep(500);
    }
}
