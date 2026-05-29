/**
 * Problem: Barrier Implementation
 * All threads wait until N arrive, then proceed together.
 * 
 * Approach: See implementation below.
 * Time Complexity: O(1) per operation
 * Space Complexity: O(n)
 * 
 * Production Analogy: MapReduce shuffle barrier - all mappers finish before reduce starts.
 */
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem14_BarrierImplementation {
    private final int parties;
    private int count = 0;
    private int generation = 0;

    public Problem14_BarrierImplementation(int parties) { this.parties = parties; }

    public synchronized void await() throws InterruptedException {
        int gen = generation;
        count++;
        if (count == parties) { count = 0; generation++; notifyAll(); }
        else { while (gen == generation) wait(); }
    }

    public static void main(String[] args) throws InterruptedException {
        Problem14_BarrierImplementation barrier = new Problem14_BarrierImplementation(3);
        for (int i = 0; i < 3; i++) {
            final int id = i;
            new Thread(() -> {
                try { System.out.println("Thread " + id + " before barrier"); barrier.await(); System.out.println("Thread " + id + " after barrier"); }
                catch (InterruptedException e) {}
            }).start();
        }
        Thread.sleep(500);
    }
}
