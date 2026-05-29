import java.util.concurrent.locks.*;
import java.util.*;

public class Problem47_BlockingQueueImplementation {
    static class BlockingQueue<T> {
        private final Queue<T> queue = new LinkedList<>();
        private final int capacity;
        private final ReentrantLock lock = new ReentrantLock();
        private final Condition notFull = lock.newCondition();
        private final Condition notEmpty = lock.newCondition();
        BlockingQueue(int cap) { this.capacity = cap; }
        void put(T item) throws InterruptedException {
            lock.lock();
            try { while (queue.size() == capacity) notFull.await(); queue.offer(item); notEmpty.signal(); }
            finally { lock.unlock(); }
        }
        T take() throws InterruptedException {
            lock.lock();
            try { while (queue.isEmpty()) notEmpty.await(); T item = queue.poll(); notFull.signal(); return item; }
            finally { lock.unlock(); }
        }
    }
    public static void main(String[] args) throws Exception {
        BlockingQueue<Integer> bq = new BlockingQueue<>(3);
        Thread p = new Thread(() -> { try { for (int i = 0; i < 5; i++) { bq.put(i); System.out.println("Put: " + i); } } catch (InterruptedException e) {} });
        Thread c = new Thread(() -> { try { for (int i = 0; i < 5; i++) { System.out.println("Take: " + bq.take()); } } catch (InterruptedException e) {} });
        p.start(); c.start(); p.join(); c.join();
    }
}
