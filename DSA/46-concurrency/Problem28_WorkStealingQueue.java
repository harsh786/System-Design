import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem28_WorkStealingQueue {
    /**
     * Problem: Work Stealing Queue
     * Each worker has own deque; steals from others when idle.
     * Approach: Per-thread Deque + random stealing from other workers.
     * Time: O(1) local op, O(n) steal scan
     * Production Analogy: ForkJoinPool in Java - work stealing for load balancing.
     */
    private final Deque<Runnable>[] queues;
    private final Thread[] workers;
    private volatile boolean running = true;

    @SuppressWarnings("unchecked")
    public Problem28_WorkStealingQueue(int numWorkers) {
        queues = new ArrayDeque[numWorkers];
        workers = new Thread[numWorkers];
        for (int i = 0; i < numWorkers; i++) {
            queues[i] = new ArrayDeque<>();
            final int id = i;
            workers[i] = new Thread(() -> {
                while (running) {
                    Runnable task = queues[id].pollFirst();
                    if (task == null) task = steal(id);
                    if (task != null) task.run();
                    else { try { Thread.sleep(10); } catch (InterruptedException e) { break; } }
                }
            }, "Worker-" + i);
            workers[i].start();
        }
    }

    private Runnable steal(int myId) {
        for (int i = 0; i < queues.length; i++) {
            if (i != myId) { synchronized (queues[i]) { Runnable t = queues[i].pollLast(); if (t != null) return t; } }
        }
        return null;
    }

    public void submit(int workerId, Runnable task) { synchronized (queues[workerId]) { queues[workerId].addFirst(task); } }

    public void shutdown() { running = false; }

    public static void main(String[] args) throws InterruptedException {
        Problem28_WorkStealingQueue ws = new Problem28_WorkStealingQueue(3);
        for (int i = 0; i < 9; i++) { final int id = i; ws.submit(0, () -> System.out.println(Thread.currentThread().getName() + " task " + id)); }
        Thread.sleep(500);
        ws.shutdown();
        System.out.println("Work stealing demo complete");
    }
}
