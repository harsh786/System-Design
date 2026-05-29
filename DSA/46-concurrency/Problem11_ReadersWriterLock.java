/**
 * Problem: Readers-Writer Lock
 * Multiple readers OR one writer at a time.
 * 
 * Approach: See implementation below.
 * Time Complexity: O(1) per operation
 * Space Complexity: O(n)
 * 
 * Production Analogy: Database read replicas - many concurrent reads, exclusive writes.
 */
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem11_ReadersWriterLock {
    private int readers = 0;
    private boolean writing = false;
    private final Object lock = new Object();

    public void readLock() throws InterruptedException {
        synchronized (lock) {
            while (writing) lock.wait();
            readers++;
        }
    }

    public void readUnlock() {
        synchronized (lock) {
            readers--;
            if (readers == 0) lock.notifyAll();
        }
    }

    public void writeLock() throws InterruptedException {
        synchronized (lock) {
            while (writing || readers > 0) lock.wait();
            writing = true;
        }
    }

    public void writeUnlock() {
        synchronized (lock) {
            writing = false;
            lock.notifyAll();
        }
    }

    public static void main(String[] args) throws InterruptedException {
        Problem11_ReadersWriterLock rwl = new Problem11_ReadersWriterLock();
        Runnable reader = () -> {
            try { rwl.readLock(); System.out.println(Thread.currentThread().getName() + " reading"); Thread.sleep(50); rwl.readUnlock(); }
            catch (InterruptedException e) {}
        };
        Runnable writer = () -> {
            try { rwl.writeLock(); System.out.println(Thread.currentThread().getName() + " writing"); Thread.sleep(50); rwl.writeUnlock(); }
            catch (InterruptedException e) {}
        };
        new Thread(reader, "R1").start(); new Thread(reader, "R2").start();
        new Thread(writer, "W1").start(); new Thread(reader, "R3").start();
        Thread.sleep(500);
    }
}
