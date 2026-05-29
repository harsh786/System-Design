/**
 * Problem: Producer-Consumer Simulation
 * Approach: Bounded buffer with synchronized access using BlockingQueue
 * Complexity: O(1) per operation
 * Production Analogy: Message queue systems (Kafka, RabbitMQ) with backpressure
 */
import java.util.concurrent.*;
public class Problem43_ProducerConsumerSimulation {
    static BlockingQueue<Integer> buffer = new ArrayBlockingQueue<>(5);

    public static void main(String[] args) throws InterruptedException {
        Thread producer = new Thread(() -> {
            for (int i = 1; i <= 10; i++) {
                try { buffer.put(i); System.out.println("Produced: " + i); }
                catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            }
        });
        Thread consumer = new Thread(() -> {
            for (int i = 0; i < 10; i++) {
                try { int val = buffer.take(); System.out.println("Consumed: " + val); }
                catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            }
        });
        producer.start(); consumer.start();
        producer.join(); consumer.join();
        System.out.println("Done");
    }
}
