import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem24_BlockingQueueWaitNotify {
    /**
     * Problem: Blocking Queue with wait/notify
     * Classic bounded buffer with intrinsic locks.
     * Time: O(1) per op
     * Production Analogy: Print spooler queue.
     */
    private final Queue<Integer> queue = new LinkedList<>();
    private final int capacity;

    public Problem24_BlockingQueueWaitNotify(int capacity) { this.capacity = capacity; }

    public synchronized void put(int val) throws InterruptedException {
        while (queue.size() == capacity) wait();
        queue.add(val);
        notifyAll();
    }

    public synchronized int take() throws InterruptedException {
        while (queue.isEmpty()) wait();
        int val = queue.poll();
        notifyAll();
        return val;
    }

    public static void main(String[] args) throws InterruptedException {
        Problem24_BlockingQueueWaitNotify q = new Problem24_BlockingQueueWaitNotify(2);
        new Thread(() -> { try { for (int i = 0; i < 4; i++) { q.put(i); System.out.println("Put " + i); } } catch (InterruptedException e) {} }).start();
        new Thread(() -> { try { Thread.sleep(100); for (int i = 0; i < 4; i++) System.out.println("Take " + q.take()); } catch (InterruptedException e) {} }).start();
        Thread.sleep(1000);
    }
}
