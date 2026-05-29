/**
 * Problem: Producer-Consumer Queue
 * Classic producer-consumer with wait/notify.
 * 
 * Approach: synchronized block with wait/notifyAll on shared buffer.
 * Time Complexity: O(1) per operation
 * Space Complexity: O(capacity)
 * 
 * Production Analogy: Message queue (RabbitMQ) - producers publish messages,
 * consumers process them asynchronously.
 */
import java.util.*;

public class Problem10_ProducerConsumerQueue {
    private final Queue<Integer> queue = new LinkedList<>();
    private final int capacity;

    public Problem10_ProducerConsumerQueue(int capacity) { this.capacity = capacity; }

    public synchronized void produce(int item) throws InterruptedException {
        while (queue.size() == capacity) wait();
        queue.add(item);
        System.out.println("Produced: " + item);
        notifyAll();
    }

    public synchronized int consume() throws InterruptedException {
        while (queue.isEmpty()) wait();
        int item = queue.poll();
        System.out.println("Consumed: " + item);
        notifyAll();
        return item;
    }

    public static void main(String[] args) throws InterruptedException {
        Problem10_ProducerConsumerQueue pc = new Problem10_ProducerConsumerQueue(3);
        Thread producer = new Thread(() -> {
            try { for (int i = 0; i < 5; i++) pc.produce(i); } catch (InterruptedException e) {}
        });
        Thread consumer = new Thread(() -> {
            try { for (int i = 0; i < 5; i++) pc.consume(); } catch (InterruptedException e) {}
        });
        producer.start(); consumer.start();
        producer.join(); consumer.join();
    }
}
