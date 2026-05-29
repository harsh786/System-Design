/**
 * Problem: Design Bounded Blocking Queue
 * Implement a thread-safe bounded queue with blocking enqueue/dequeue.
 * 
 * Approach: ReentrantLock with two Conditions (notFull, notEmpty).
 * Time Complexity: O(1) per operation
 * Space Complexity: O(capacity)
 * 
 * Production Analogy: Message broker buffer (Kafka partition buffer) -
 * producers block when buffer full, consumers block when empty.
 */
import java.util.concurrent.locks.*;
import java.util.LinkedList;

public class Problem06_DesignBoundedBlockingQueue {
    private LinkedList<Integer> queue = new LinkedList<>();
    private int capacity;
    private ReentrantLock lock = new ReentrantLock();
    private Condition notFull = lock.newCondition();
    private Condition notEmpty = lock.newCondition();

    public Problem06_DesignBoundedBlockingQueue(int capacity) { this.capacity = capacity; }

    public void enqueue(int element) throws InterruptedException {
        lock.lock();
        try {
            while (queue.size() == capacity) notFull.await();
            queue.addLast(element);
            notEmpty.signal();
        } finally { lock.unlock(); }
    }

    public int dequeue() throws InterruptedException {
        lock.lock();
        try {
            while (queue.isEmpty()) notEmpty.await();
            int val = queue.removeFirst();
            notFull.signal();
            return val;
        } finally { lock.unlock(); }
    }

    public int size() {
        lock.lock();
        try { return queue.size(); } finally { lock.unlock(); }
    }

    public static void main(String[] args) throws InterruptedException {
        Problem06_DesignBoundedBlockingQueue bq = new Problem06_DesignBoundedBlockingQueue(3);
        Thread producer = new Thread(() -> {
            try { for (int i = 0; i < 5; i++) { bq.enqueue(i); System.out.println("Produced: " + i); } }
            catch (InterruptedException e) {}
        });
        Thread consumer = new Thread(() -> {
            try { for (int i = 0; i < 5; i++) { System.out.println("Consumed: " + bq.dequeue()); } }
            catch (InterruptedException e) {}
        });
        producer.start(); consumer.start();
        producer.join(); consumer.join();
    }
}
