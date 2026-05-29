import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;
import java.util.stream.*;

public class Problem48_ConcurrentLinkedQueue {
    /**
     * Problem: Concurrent Linked Queue (Michael-Scott)
     * Lock-free queue using CAS on head/tail.
     * Time: O(1) amortized | Space: O(n)
     * Production Analogy: Java's ConcurrentLinkedQueue, used in executor task queues.
     */
    private static class Node { final int val; final AtomicReference<Node> next; Node(int v) { val = v; next = new AtomicReference<>(null); } }
    private final AtomicReference<Node> head, tail;

    public Problem48_ConcurrentLinkedQueue() {
        Node sentinel = new Node(0);
        head = new AtomicReference<>(sentinel);
        tail = new AtomicReference<>(sentinel);
    }

    public void enqueue(int val) {
        Node newNode = new Node(val);
        while (true) {
            Node t = tail.get(); Node next = t.next.get();
            if (next == null) { if (t.next.compareAndSet(null, newNode)) { tail.compareAndSet(t, newNode); return; } }
            else { tail.compareAndSet(t, next); }
        }
    }

    public Integer dequeue() {
        while (true) {
            Node h = head.get(); Node t = tail.get(); Node next = h.next.get();
            if (h == t) { if (next == null) return null; tail.compareAndSet(t, next); }
            else { int val = next.val; if (head.compareAndSet(h, next)) return val; }
        }
    }

    public static void main(String[] args) throws InterruptedException {
        Problem48_ConcurrentLinkedQueue q = new Problem48_ConcurrentLinkedQueue();
        Thread prod = new Thread(() -> { for (int i = 0; i < 5; i++) q.enqueue(i); });
        prod.start(); prod.join();
        Integer v; while ((v = q.dequeue()) != null) System.out.println("Dequeued: " + v);
    }
}
