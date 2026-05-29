import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem25_BoundedBufferProblem {
    /**
     * Problem: Bounded Buffer Problem
     * Classic OS problem - fixed size buffer shared between producers and consumers.
     * Approach: Semaphores for empty/full slots + mutex.
     * Time: O(1) per op
     * Production Analogy: Streaming video buffer between decoder and renderer.
     */
    private final int[] buffer;
    private int in = 0, out = 0;
    private final Semaphore empty, full, mutex;

    public Problem25_BoundedBufferProblem(int size) {
        buffer = new int[size];
        empty = new Semaphore(size);
        full = new Semaphore(0);
        mutex = new Semaphore(1);
    }

    public void produce(int item) throws InterruptedException {
        empty.acquire(); mutex.acquire();
        buffer[in] = item; in = (in + 1) % buffer.length;
        mutex.release(); full.release();
    }

    public int consume() throws InterruptedException {
        full.acquire(); mutex.acquire();
        int item = buffer[out]; out = (out + 1) % buffer.length;
        mutex.release(); empty.release();
        return item;
    }

    public static void main(String[] args) throws InterruptedException {
        Problem25_BoundedBufferProblem bb = new Problem25_BoundedBufferProblem(3);
        new Thread(() -> { try { for (int i = 0; i < 5; i++) { bb.produce(i); System.out.println("Produced " + i); } } catch (InterruptedException e) {} }).start();
        new Thread(() -> { try { for (int i = 0; i < 5; i++) System.out.println("Consumed " + bb.consume()); } catch (InterruptedException e) {} }).start();
        Thread.sleep(500);
    }
}
