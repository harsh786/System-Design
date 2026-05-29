import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem21_CountDownLatchFromScratch {
    /**
     * Problem: CountDownLatch from Scratch
     * Implement countdown latch using wait/notify.
     * Approach: Counter with synchronized decrement, await blocks until 0.
     * Time: O(1) countDown, O(waiting) await
     * Production Analogy: Service startup - wait for all dependencies to be ready.
     */
    private int count;

    public Problem21_CountDownLatchFromScratch(int count) { this.count = count; }

    public synchronized void countDown() {
        count--;
        if (count == 0) notifyAll();
    }

    public synchronized void await() throws InterruptedException {
        while (count > 0) wait();
    }

    public static void main(String[] args) throws InterruptedException {
        Problem21_CountDownLatchFromScratch latch = new Problem21_CountDownLatchFromScratch(3);
        for (int i = 0; i < 3; i++) {
            final int id = i;
            new Thread(() -> { System.out.println("Worker " + id + " done"); latch.countDown(); }).start();
        }
        latch.await();
        System.out.println("All workers finished!");
    }
}
