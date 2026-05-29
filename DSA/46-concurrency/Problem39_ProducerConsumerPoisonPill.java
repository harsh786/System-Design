import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem39_ProducerConsumerPoisonPill {
    /**
     * Problem: Producer-Consumer with Poison Pill
     * Graceful shutdown using sentinel value.
     * Time: O(1) per op | Space: O(queue_size)
     * Production Analogy: Graceful shutdown of message consumer (drain queue, then stop).
     */
    private static final int POISON_PILL = Integer.MIN_VALUE;

    public static void main(String[] args) throws InterruptedException {
        BlockingQueue<Integer> queue = new LinkedBlockingQueue<>(10);
        Thread producer = new Thread(() -> {
            try {
                for (int i = 0; i < 10; i++) { queue.put(i); System.out.println("Produced: " + i); }
                queue.put(POISON_PILL);
            } catch (InterruptedException e) {}
        });
        Thread consumer = new Thread(() -> {
            try {
                while (true) { int val = queue.take(); if (val == POISON_PILL) { System.out.println("Got poison pill, shutting down"); break; } System.out.println("Consumed: " + val); }
            } catch (InterruptedException e) {}
        });
        producer.start(); consumer.start();
        producer.join(); consumer.join();
    }
}
