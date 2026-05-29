/**
 * Problem: Deadlock Prevention Lock Ordering
 * Prevent deadlock by always acquiring locks in consistent order.
 * 
 * Approach: See implementation below.
 * Time Complexity: O(1) per operation
 * Space Complexity: O(n)
 * 
 * Production Analogy: Database transaction ordering to prevent distributed deadlocks.
 */
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem15_DeadlockPreventionLockOrdering {
    private final Object lock1 = new Object();
    private final Object lock2 = new Object();
    private int account1 = 1000, account2 = 1000;

    public void transfer(boolean fromOneToTwo, int amount) {
        Object first = fromOneToTwo ? lock1 : lock2;
        Object second = fromOneToTwo ? lock2 : lock1;
        synchronized (first) {
            synchronized (second) {
                if (fromOneToTwo) { account1 -= amount; account2 += amount; }
                else { account2 -= amount; account1 += amount; }
                System.out.println("Transfer done. A1=" + account1 + " A2=" + account2);
            }
        }
    }

    public static void main(String[] args) throws InterruptedException {
        Problem15_DeadlockPreventionLockOrdering obj = new Problem15_DeadlockPreventionLockOrdering();
        Thread t1 = new Thread(() -> { for (int i = 0; i < 100; i++) obj.transfer(true, 10); });
        Thread t2 = new Thread(() -> { for (int i = 0; i < 100; i++) obj.transfer(false, 10); });
        t1.start(); t2.start(); t1.join(); t2.join();
        System.out.println("Final: A1=" + obj.account1 + " A2=" + obj.account2);
    }
}
