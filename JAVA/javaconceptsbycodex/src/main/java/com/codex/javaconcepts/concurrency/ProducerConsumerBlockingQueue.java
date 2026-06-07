package com.codex.javaconcepts.concurrency;

import java.util.List;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;

public class ProducerConsumerBlockingQueue {
    private static final String POISON_PILL = "__STOP__";

    public static void main(String[] args) throws InterruptedException {
        BlockingQueue<String> queue = new ArrayBlockingQueue<>(2);

        Thread producer = new Thread(() -> produce(queue), "producer");
        Thread consumer = new Thread(() -> consume(queue), "consumer");

        consumer.start();
        producer.start();

        producer.join();
        consumer.join();
    }

    private static void produce(BlockingQueue<String> queue) {
        try {
            for (String job : List.of("email", "invoice", "ledger-sync")) {
                queue.put(job);
                System.out.println("Produced: " + job);
            }
            queue.put(POISON_PILL);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
        }
    }

    private static void consume(BlockingQueue<String> queue) {
        try {
            while (true) {
                String job = queue.take();
                if (POISON_PILL.equals(job)) {
                    System.out.println("Consumer stopping");
                    return;
                }
                System.out.println("Consumed: " + job);
            }
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
        }
    }
}

