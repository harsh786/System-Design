import java.util.concurrent.*;
import java.util.*;

public class Problem19_ProducerConsumerBoundedQueue {
    static class BoundedQueue<T> {
        private final Queue<T> q = new LinkedList<>();
        private final int capacity;
        private final Object lock = new Object();
        BoundedQueue(int cap) { this.capacity = cap; }
        void put(T item) throws InterruptedException {
            synchronized (lock) {
                while (q.size() == capacity) lock.wait();
                q.offer(item); lock.notifyAll();
            }
        }
        T take() throws InterruptedException {
            synchronized (lock) {
                while (q.isEmpty()) lock.wait();
                T item = q.poll(); lock.notifyAll(); return item;
            }
        }
        int size() { synchronized (lock) { return q.size(); } }
    }
    public static void main(String[] args) throws Exception {
        BoundedQueue<Integer> bq = new BoundedQueue<>(5);
        Thread producer = new Thread(() -> { try { for (int i = 0; i < 10; i++) { bq.put(i); System.out.println("Produced: " + i); } } catch (InterruptedException e) {} });
        Thread consumer = new Thread(() -> { try { for (int i = 0; i < 10; i++) { System.out.println("Consumed: " + bq.take()); } } catch (InterruptedException e) {} });
        producer.start(); consumer.start(); producer.join(); consumer.join();
    }
}
