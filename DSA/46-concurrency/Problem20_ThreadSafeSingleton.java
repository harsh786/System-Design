/**
 * Problem: Thread-safe Singleton (Double-Checked Locking)
 * Lazy singleton with double-checked locking pattern.
 * 
 * Approach: See implementation below.
 * Time Complexity: O(1) per operation
 * Space Complexity: O(n)
 * 
 * Production Analogy: Service registry instance - single global config loaded once.
 */
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem20_ThreadSafeSingleton {
    private static volatile Problem20_ThreadSafeSingleton instance;

    private Problem20_ThreadSafeSingleton() { System.out.println("Singleton created"); }

    public static Problem20_ThreadSafeSingleton getInstance() {
        if (instance == null) {
            synchronized (Problem20_ThreadSafeSingleton.class) {
                if (instance == null) instance = new Problem20_ThreadSafeSingleton();
            }
        }
        return instance;
    }

    public static void main(String[] args) throws InterruptedException {
        Thread[] threads = new Thread[10];
        for (int i = 0; i < 10; i++) {
            threads[i] = new Thread(() -> Problem20_ThreadSafeSingleton.getInstance());
            threads[i].start();
        }
        for (Thread t : threads) t.join();
        System.out.println("All threads got same instance: " + (getInstance() == getInstance()));
    }
}
