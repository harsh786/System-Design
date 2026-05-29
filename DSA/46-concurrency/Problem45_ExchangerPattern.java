import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;
import java.util.stream.*;

public class Problem45_ExchangerPattern {
    /**
     * Problem: Exchanger Pattern
     * Two threads exchange data at a synchronization point.
     * Time: O(1) | Space: O(1)
     * Production Analogy: Double buffering - one thread fills buffer while other processes previous.
     */
    public static void main(String[] args) throws InterruptedException {
        Exchanger<String> exchanger = new Exchanger<>();
        Thread producer = new Thread(() -> {
            try {
                for (int i = 0; i < 3; i++) {
                    String data = "Batch-" + i;
                    System.out.println("Producer sending: " + data);
                    String received = exchanger.exchange(data);
                    System.out.println("Producer got back: " + received);
                }
            } catch (InterruptedException e) {}
        });
        Thread consumer = new Thread(() -> {
            try {
                for (int i = 0; i < 3; i++) {
                    String received = exchanger.exchange("ACK-" + i);
                    System.out.println("Consumer received: " + received);
                }
            } catch (InterruptedException e) {}
        });
        producer.start(); consumer.start();
        producer.join(); consumer.join();
    }
}
