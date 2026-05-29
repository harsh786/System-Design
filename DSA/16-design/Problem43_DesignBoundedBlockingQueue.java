import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

/**
 * Problem 43: Design Bounded Blocking Queue
 * 
 * API Contract:
 * - enqueue(element): Block if full until space available
 * - dequeue(): Block if empty until element available
 * - size(): Return current size
 * 
 * Complexity: O(1) per operation (excluding blocking time)
 * Data Structure: Circular buffer with ReentrantLock + Conditions
 * 
 * Production Analogy: Java's ArrayBlockingQueue, Kafka partition buffers,
 * producer-consumer pattern, thread pool work queues, Go channels
 */
public class Problem43_DesignBoundedBlockingQueue {

    static class BoundedBlockingQueue {
        private Queue<Integer> queue;
        private int capacity;
        private ReentrantLock lock;
        private Condition notFull, notEmpty;

        public BoundedBlockingQueue(int capacity) {
            this.capacity = capacity;
            queue = new LinkedList<>();
            lock = new ReentrantLock();
            notFull = lock.newCondition();
            notEmpty = lock.newCondition();
        }

        public void enqueue(int element) throws InterruptedException {
            lock.lock();
            try {
                while (queue.size() == capacity) notFull.await();
                queue.offer(element);
                notEmpty.signal();
            } finally {
                lock.unlock();
            }
        }

        public int dequeue() throws InterruptedException {
            lock.lock();
            try {
                while (queue.isEmpty()) notEmpty.await();
                int val = queue.poll();
                notFull.signal();
                return val;
            } finally {
                lock.unlock();
            }
        }

        public int size() {
            lock.lock();
            try { return queue.size(); }
            finally { lock.unlock(); }
        }
    }

    public static void main(String[] args) throws Exception {
        BoundedBlockingQueue bq = new BoundedBlockingQueue(3);
        bq.enqueue(1); bq.enqueue(2); bq.enqueue(3);
        assert bq.size() == 3;
        assert bq.dequeue() == 1;
        assert bq.size() == 2;
        bq.enqueue(4);
        assert bq.dequeue() == 2;
        assert bq.dequeue() == 3;
        assert bq.dequeue() == 4;
        assert bq.size() == 0;

        // Concurrent test
        BoundedBlockingQueue bq2 = new BoundedBlockingQueue(2);
        AtomicInteger sum = new AtomicInteger(0);
        Thread producer = new Thread(() -> {
            try { for (int i = 1; i <= 5; i++) bq2.enqueue(i); }
            catch (InterruptedException e) {}
        });
        Thread consumer = new Thread(() -> {
            try { for (int i = 0; i < 5; i++) sum.addAndGet(bq2.dequeue()); }
            catch (InterruptedException e) {}
        });
        producer.start(); consumer.start();
        producer.join(); consumer.join();
        assert sum.get() == 15; // 1+2+3+4+5

        System.out.println("All tests passed!");
    }
}
