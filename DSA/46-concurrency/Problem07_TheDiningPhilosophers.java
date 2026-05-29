/**
 * Problem: The Dining Philosophers
 * 5 philosophers alternate between thinking and eating, sharing forks.
 * 
 * Approach: Resource ordering - always pick lower-numbered fork first to prevent deadlock.
 * Time Complexity: O(1) per action
 * Space Complexity: O(n) for locks
 * 
 * Production Analogy: Multiple services needing shared resources (DB connections, locks).
 * Ordering lock acquisition prevents distributed deadlocks.
 */
import java.util.concurrent.locks.*;

public class Problem07_TheDiningPhilosophers {
    private ReentrantLock[] forks = new ReentrantLock[5];

    public Problem07_TheDiningPhilosophers() {
        for (int i = 0; i < 5; i++) forks[i] = new ReentrantLock();
    }

    public void wantsToEat(int philosopher) throws InterruptedException {
        int left = philosopher;
        int right = (philosopher + 1) % 5;
        int first = Math.min(left, right);
        int second = Math.max(left, right);
        forks[first].lock();
        forks[second].lock();
        try {
            System.out.println("Philosopher " + philosopher + " is eating");
            Thread.sleep(10);
        } finally {
            forks[second].unlock();
            forks[first].unlock();
        }
    }

    public static void main(String[] args) throws InterruptedException {
        Problem07_TheDiningPhilosophers dp = new Problem07_TheDiningPhilosophers();
        Thread[] threads = new Thread[5];
        for (int i = 0; i < 5; i++) {
            final int id = i;
            threads[i] = new Thread(() -> {
                try { for (int j = 0; j < 3; j++) dp.wantsToEat(id); }
                catch (InterruptedException e) {}
            });
            threads[i].start();
        }
        for (Thread t : threads) t.join();
        System.out.println("All done - no deadlock!");
    }
}
