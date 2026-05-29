import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem22_CyclicBarrierFromScratch {
    /**
     * Problem: CyclicBarrier from Scratch
     * Reusable barrier for N threads.
     * Approach: Counter resets after all threads arrive.
     * Time: O(1) per await
     * Production Analogy: Game tick synchronization - all players' moves processed before next frame.
     */
    private final int parties;
    private int count;
    private int generation = 0;

    public Problem22_CyclicBarrierFromScratch(int parties) { this.parties = parties; this.count = 0; }

    public synchronized void await() throws InterruptedException {
        int gen = generation;
        count++;
        if (count == parties) { count = 0; generation++; notifyAll(); }
        else { while (gen == generation) wait(); }
    }

    public static void main(String[] args) throws InterruptedException {
        Problem22_CyclicBarrierFromScratch barrier = new Problem22_CyclicBarrierFromScratch(3);
        for (int i = 0; i < 3; i++) {
            final int id = i;
            new Thread(() -> {
                try {
                    System.out.println("T" + id + " phase 1"); barrier.await();
                    System.out.println("T" + id + " phase 2"); barrier.await();
                    System.out.println("T" + id + " done");
                } catch (InterruptedException e) {}
            }).start();
        }
        Thread.sleep(500);
    }
}
