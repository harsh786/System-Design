import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem23_BlockingQueueReentrantLock {
    /**
     * Problem: Blocking Queue with ReentrantLock
     * Bounded blocking queue using ReentrantLock + Conditions.
     * Time: O(1) per op
     * Production Analogy: Kafka internal buffer between network thread and IO thread.
     */
    private final int[] buffer;
    private int head, tail, size;
    private final ReentrantLock lock = new ReentrantLock();
    private final Condition notFull = lock.newCondition();
    private final Condition notEmpty = lock.newCondition();

    public Problem23_BlockingQueueReentrantLock(int cap) { buffer = new int[cap]; }

    public void put(int val) throws InterruptedException {
        lock.lock();
        try { while (size == buffer.length) notFull.await(); buffer[tail] = val; tail = (tail + 1) % buffer.length; size++; notEmpty.signal(); }
        finally { lock.unlock(); }
    }

    public int take() throws InterruptedException {
        lock.lock();
        try { while (size == 0) notEmpty.await(); int val = buffer[head]; head = (head + 1) % buffer.length; size--; notFull.signal(); return val; }
        finally { lock.unlock(); }
    }

    public static void main(String[] args) throws InterruptedException {
        Problem23_BlockingQueueReentrantLock q = new Problem23_BlockingQueueReentrantLock(3);
        new Thread(() -> { try { for (int i = 0; i < 5; i++) { q.put(i); System.out.println("Put " + i); } } catch (InterruptedException e) {} }).start();
        new Thread(() -> { try { for (int i = 0; i < 5; i++) System.out.println("Take " + q.take()); } catch (InterruptedException e) {} }).start();
        Thread.sleep(500);
    }
}
