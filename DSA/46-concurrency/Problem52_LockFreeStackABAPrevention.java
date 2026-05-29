import java.util.concurrent.atomic.AtomicStampedReference;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Problem 52: Lock-Free Stack with ABA Prevention (Stamped Reference)
 * 
 * REAL-WORLD USAGE:
 * - Memory allocators (free lists in jemalloc, tcmalloc)
 * - Object pools in game engines and high-frequency trading
 * - Thread-local garbage collection free lists
 * 
 * THE ABA PROBLEM:
 * 1. Thread A reads top = node X, prepares to CAS(X, X.next)
 * 2. Thread B pops X, pops Y, pushes X back (X is on top again)
 * 3. Thread A's CAS succeeds (top is X!) but X.next is WRONG (stale)
 * 4. Stack is corrupted - nodes lost or circular reference formed
 * 
 * SOLUTION: AtomicStampedReference pairs a pointer with a version stamp.
 * CAS only succeeds if BOTH reference AND stamp match expected values.
 * Every modification increments the stamp, so ABA is detected.
 * 
 * MEMORY ORDERING:
 * - AtomicStampedReference.compareAndSet is a full fence
 * - The stamp acts as a logical clock for the pointer
 * - In languages without GC (C/C++), this is critical; in Java, GC prevents
 *   literal ABA on heap objects, but the pattern is still important for
 *   pool-based allocation where objects are recycled
 * 
 * PITFALLS:
 * 1. Stamp overflow: int wraps around after 2^31 operations (practically safe)
 * 2. AtomicStampedReference allocates an internal Pair object on every set
 *    (may cause GC pressure in ultra-hot paths)
 * 3. False sharing if nodes are allocated close together in memory
 */
public class Problem52_LockFreeStackABAPrevention<T> {

    private static class Node<T> {
        final T value;
        Node<T> next;

        Node(T value) {
            this.value = value;
        }
    }

    // AtomicStampedReference = (reference, int stamp) updated atomically
    private final AtomicStampedReference<Node<T>> top;

    public Problem52_LockFreeStackABAPrevention() {
        top = new AtomicStampedReference<>(null, 0);
    }

    public void push(T value) {
        Node<T> newNode = new Node<>(value);
        while (true) {
            int[] stampHolder = new int[1];
            Node<T> curTop = top.get(stampHolder);
            int curStamp = stampHolder[0];
            newNode.next = curTop;
            // CAS checks both reference equality AND stamp equality
            if (top.compareAndSet(curTop, newNode, curStamp, curStamp + 1)) {
                return;
            }
            // If CAS fails, either another push/pop happened, or ABA was prevented
        }
    }

    public T pop() {
        while (true) {
            int[] stampHolder = new int[1];
            Node<T> curTop = top.get(stampHolder);
            int curStamp = stampHolder[0];
            if (curTop == null) {
                return null; // Stack empty
            }
            Node<T> next = curTop.next;
            // Without stamped reference, ABA could cause curTop.next to be stale
            if (top.compareAndSet(curTop, next, curStamp, curStamp + 1)) {
                return curTop.value;
            }
        }
    }

    public boolean isEmpty() {
        return top.getReference() == null;
    }

    // ==================== ABA DEMONSTRATION ====================
    /**
     * Demonstrates the ABA scenario:
     * Without stamps, this would corrupt the stack.
     * With stamps, the CAS correctly fails when ABA occurs.
     */
    private static void demonstrateABA() throws InterruptedException {
        System.out.println("\n--- ABA Scenario Demonstration ---");
        Problem52_LockFreeStackABAPrevention<String> stack = new Problem52_LockFreeStackABAPrevention<>();
        stack.push("A");
        stack.push("B");
        stack.push("C");
        // Stack: C -> B -> A

        // Thread 1 reads top (C), then gets preempted
        int[] stamp = new int[1];
        // Simulate: thread sees top = C with stamp
        System.out.println("Initial top stamp: " + stack.top.getStamp());

        // Thread 2 pops C, pops B, pushes C back
        stack.pop(); // removes C
        stack.pop(); // removes B
        stack.push("C"); // pushes C back - ABA!
        // Stack: C -> A (B is lost!)

        System.out.println("After ABA manipulation, stamp: " + stack.top.getStamp());
        System.out.println("Stamp changed from 0 to " + stack.top.getStamp() + " - ABA detected!");
        // Thread 1's CAS would fail because stamp changed (0 != 3)
    }

    // ==================== STRESS TEST ====================
    public static void main(String[] args) throws InterruptedException {
        demonstrateABA();

        System.out.println("\n=== Lock-Free Stack (ABA-safe) Stress Test ===");
        Problem52_LockFreeStackABAPrevention<Integer> stack = new Problem52_LockFreeStackABAPrevention<>();
        int numThreads = 8;
        int opsPerThread = 200_000;
        AtomicInteger pushCount = new AtomicInteger(0);
        AtomicInteger popCount = new AtomicInteger(0);
        CountDownLatch startLatch = new CountDownLatch(1);
        CountDownLatch doneLatch = new CountDownLatch(numThreads);

        for (int t = 0; t < numThreads; t++) {
            new Thread(() -> {
                try { startLatch.await(); } catch (InterruptedException e) { return; }
                for (int i = 0; i < opsPerThread; i++) {
                    if (i % 2 == 0) {
                        stack.push(i);
                        pushCount.incrementAndGet();
                    } else {
                        if (stack.pop() != null) {
                            popCount.incrementAndGet();
                        }
                    }
                }
                doneLatch.countDown();
            }).start();
        }

        long start = System.nanoTime();
        startLatch.countDown();
        doneLatch.await();
        long elapsed = System.nanoTime() - start;

        // Drain remaining
        int remaining = 0;
        while (stack.pop() != null) remaining++;

        System.out.println("Threads: " + numThreads + ", Ops/thread: " + opsPerThread);
        System.out.println("Pushes: " + pushCount.get() + ", Successful pops: " + popCount.get());
        System.out.println("Remaining in stack: " + remaining);
        System.out.println("Integrity check (push == pop + remaining): " +
                (pushCount.get() == popCount.get() + remaining));
        System.out.println("Time: " + (elapsed / 1_000_000) + " ms");
        System.out.println("Final stamp value: " + stack.top.getStamp());
    }
}
