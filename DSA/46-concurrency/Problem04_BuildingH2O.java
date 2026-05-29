/**
 * Problem: Building H2O
 * Threads call hydrogen() or oxygen(). Group them as H2O (2 hydrogen + 1 oxygen).
 * 
 * Approach: Use Semaphores - oxygen waits for 2 hydrogen, barrier resets per molecule.
 * Time Complexity: O(1) per call
 * Space Complexity: O(1)
 * 
 * Production Analogy: Batch processing - wait for all required components before
 * assembling an order (e.g., 2 items + 1 box = 1 shipment).
 */
import java.util.concurrent.*;

public class Problem04_BuildingH2O {
    private Semaphore hSem = new Semaphore(2);
    private Semaphore oSem = new Semaphore(0);
    private CyclicBarrier barrier = new CyclicBarrier(3, () -> {
        hSem.release(2);
    });

    public void hydrogen(Runnable releaseHydrogen) throws InterruptedException {
        hSem.acquire();
        releaseHydrogen.run();
        try { barrier.await(); } catch (BrokenBarrierException e) {}
    }

    public void oxygen(Runnable releaseOxygen) throws InterruptedException {
        oSem.acquire();
        releaseOxygen.run();
        try { barrier.await(); } catch (BrokenBarrierException e) {}
    }

    public static void main(String[] args) throws InterruptedException {
        // Simplified demo
        Problem04_BuildingH2O obj = new Problem04_BuildingH2O();
        // In real scenario, multiple threads call hydrogen/oxygen
        System.out.println("Building H2O - semaphore + barrier approach");
        System.out.println("2 hydrogen threads + 1 oxygen thread form one molecule");
    }
}
