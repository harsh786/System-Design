/**
 * Problem: Print Zero Even Odd
 * Three threads: one prints 0, one prints even, one prints odd -> 0102030405...
 * 
 * Approach: Use three Semaphores to coordinate printing order.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Traffic light controller coordinating multiple signal phases.
 */
import java.util.concurrent.*;

public class Problem03_PrintZeroEvenOdd {
    private int n;
    private Semaphore zeroSem = new Semaphore(1);
    private Semaphore oddSem = new Semaphore(0);
    private Semaphore evenSem = new Semaphore(0);

    public Problem03_PrintZeroEvenOdd(int n) { this.n = n; }

    public void zero() throws InterruptedException {
        for (int i = 1; i <= n; i++) {
            zeroSem.acquire();
            System.out.print(0);
            if (i % 2 == 1) oddSem.release();
            else evenSem.release();
        }
    }

    public void odd() throws InterruptedException {
        for (int i = 1; i <= n; i += 2) {
            oddSem.acquire();
            System.out.print(i);
            zeroSem.release();
        }
    }

    public void even() throws InterruptedException {
        for (int i = 2; i <= n; i += 2) {
            evenSem.acquire();
            System.out.print(i);
            zeroSem.release();
        }
    }

    public static void main(String[] args) throws InterruptedException {
        Problem03_PrintZeroEvenOdd obj = new Problem03_PrintZeroEvenOdd(5);
        Thread t1 = new Thread(() -> { try { obj.zero(); } catch (InterruptedException e) {} });
        Thread t2 = new Thread(() -> { try { obj.odd(); } catch (InterruptedException e) {} });
        Thread t3 = new Thread(() -> { try { obj.even(); } catch (InterruptedException e) {} });
        t1.start(); t2.start(); t3.start();
        t1.join(); t2.join(); t3.join();
        System.out.println();
    }
}
