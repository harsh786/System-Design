import java.util.concurrent.atomic.*;
import java.util.concurrent.*;
import java.util.Random;

/**
 * Problem 60: Elimination Backoff Stack
 * 
 * REAL-WORLD USAGE:
 * - High-contention concurrent stacks in trading systems
 * - Object pools under heavy contention
 * - Any paired producer-consumer pattern where operations can cancel out
 * 
 * KEY CONCEPTS:
 * - Under low contention: use a normal lock-free stack (CAS on top)
 * - Under high contention: use an ELIMINATION ARRAY as a backoff mechanism
 * - A push and a pop can "eliminate" each other without touching the stack!
 *   Push puts item in elimination array, Pop takes it directly → both complete
 * - This turns contention from a problem into an ADVANTAGE
 * 
 * HOW ELIMINATION WORKS:
 * 1. Thread fails CAS on stack (contention detected)
 * 2. Thread goes to a random slot in the elimination array
 * 3. Pusher: deposits value in slot, waits for a popper to take it
 * 4. Popper: looks for a value in slot, takes it if found
 * 5. If no match within timeout, fall back to retrying the stack
 * 
 * MEMORY ORDERING:
 * - Elimination array slots use AtomicReference (volatile semantics)
 * - The CAS on a slot establishes happens-before between push and pop
 * - Data exchanged through the slot is safely published
 * 
 * PITFALLS:
 * 1. Elimination only helps when push and pop rates are balanced
 * 2. Array size matters: too small = contention on array, too large = low match rate
 * 3. Timeout tuning: too short = miss eliminations, too long = added latency
 */
public class Problem60_EliminationBackoffStack<T> {

    private static final int ELIMINATION_ARRAY_SIZE = 16;
    private static final long ELIMINATION_TIMEOUT_NS = 1000; // 1 microsecond

    // ==================== LOCK-FREE STACK ====================
    private static class Node<T> {
        final T value;
        Node<T> next;
        Node(T value) { this.value = value; }
    }

    private final AtomicReference<Node<T>> top = new AtomicReference<>(null);

    // ==================== ELIMINATION ARRAY ====================
    // Each slot: null = empty, WAITING = pusher waiting, value = ready to exchange
    @SuppressWarnings("unchecked")
    private final AtomicReference<Object>[] eliminationArray = new AtomicReference[ELIMINATION_ARRAY_SIZE];
    private static final Object WAITING = new Object(); // Sentinel

    // Stats
    private final AtomicLong eliminationSuccesses = new AtomicLong(0);
    private final AtomicLong stackSuccesses = new AtomicLong(0);

    public Problem60_EliminationBackoffStack() {
        for (int i = 0; i < ELIMINATION_ARRAY_SIZE; i++) {
            eliminationArray[i] = new AtomicReference<>(null);
        }
    }

    public void push(T value) {
        // Try the stack first
        Node<T> newNode = new Node<>(value);
        if (tryPush(newNode)) {
            stackSuccesses.incrementAndGet();
            return;
        }

        // Contention detected - try elimination
        if (tryEliminatePush(value)) {
            eliminationSuccesses.incrementAndGet();
            return;
        }

        // Elimination failed - keep retrying the stack
        while (!tryPush(newNode)) {
            Thread.onSpinWait();
        }
        stackSuccesses.incrementAndGet();
    }

    public T pop() {
        // Try the stack first
        T result = tryPop();
        if (result != null) {
            stackSuccesses.incrementAndGet();
            return result;
        }

        // Try elimination (find a pusher)
        result = tryEliminatePop();
        if (result != null) {
            eliminationSuccesses.incrementAndGet();
            return result;
        }

        // Keep retrying
        while (true) {
            result = tryPop();
            if (result != null) {
                stackSuccesses.incrementAndGet();
                return result;
            }
            // Try elimination again
            result = tryEliminatePop();
            if (result != null) {
                eliminationSuccesses.incrementAndGet();
                return result;
            }
            Thread.onSpinWait();
        }
    }

    private boolean tryPush(Node<T> node) {
        Node<T> curTop = top.get();
        node.next = curTop;
        return top.compareAndSet(curTop, node);
    }

    private T tryPop() {
        Node<T> curTop = top.get();
        if (curTop == null) return null;
        if (top.compareAndSet(curTop, curTop.next)) {
            return curTop.value;
        }
        return null;
    }

    /**
     * Pusher: deposit value in a random slot, wait for popper to take it.
     */
    private boolean tryEliminatePush(T value) {
        int slot = ThreadLocalRandom.current().nextInt(ELIMINATION_ARRAY_SIZE);
        AtomicReference<Object> ref = eliminationArray[slot];

        // Try to deposit our value
        if (ref.compareAndSet(null, value)) {
            // Wait for a popper to take it
            long deadline = System.nanoTime() + ELIMINATION_TIMEOUT_NS;
            while (System.nanoTime() < deadline) {
                if (ref.get() == null) {
                    // Popper took our value!
                    return true;
                }
                Thread.onSpinWait();
            }
            // Timeout - try to reclaim our value
            if (ref.compareAndSet(value, null)) {
                return false; // We took it back - no elimination
            }
            // Someone else took it between timeout check and reclaim
            return true;
        }
        return false;
    }

    /**
     * Popper: look for a value in a random slot, take it if found.
     */
    @SuppressWarnings("unchecked")
    private T tryEliminatePop() {
        int slot = ThreadLocalRandom.current().nextInt(ELIMINATION_ARRAY_SIZE);
        AtomicReference<Object> ref = eliminationArray[slot];

        Object value = ref.get();
        if (value != null && value != WAITING) {
            // Found a pusher's value - try to take it
            if (ref.compareAndSet(value, null)) {
                return (T) value;
            }
        }
        return null;
    }

    // ==================== STRESS TEST ====================
    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Elimination Backoff Stack ===\n");

        Problem60_EliminationBackoffStack<Integer> stack = new Problem60_EliminationBackoffStack<>();
        int numThreads = 16; // High thread count to trigger elimination
        int opsPerThread = 200_000;
        AtomicInteger pushCount = new AtomicInteger(0);
        AtomicInteger popCount = new AtomicInteger(0);
        CountDownLatch startLatch = new CountDownLatch(1);
        CountDownLatch doneLatch = new CountDownLatch(numThreads);

        // Half pushers, half poppers (balanced = good elimination rate)
        for (int t = 0; t < numThreads; t++) {
            final boolean isPusher = (t % 2 == 0);
            new Thread(() -> {
                try { startLatch.await(); } catch (InterruptedException e) { return; }
                for (int i = 0; i < opsPerThread; i++) {
                    if (isPusher) {
                        stack.push(i);
                        pushCount.incrementAndGet();
                    } else {
                        Integer val = stack.pop();
                        if (val != null) popCount.incrementAndGet();
                    }
                }
                doneLatch.countDown();
            }).start();
        }

        long start = System.nanoTime();
        startLatch.countDown();
        doneLatch.await();
        long elapsed = System.nanoTime() - start;

        System.out.println("Threads: " + numThreads + " (" + numThreads/2 + " pushers, " + numThreads/2 + " poppers)");
        System.out.println("Ops/thread: " + opsPerThread);
        System.out.println("Pushes: " + pushCount.get() + ", Pops: " + popCount.get());
        System.out.println("Elimination successes: " + stack.eliminationSuccesses.get());
        System.out.println("Stack successes: " + stack.stackSuccesses.get());
        long totalOps = stack.eliminationSuccesses.get() + stack.stackSuccesses.get();
        System.out.println("Elimination rate: " +
                (stack.eliminationSuccesses.get() * 100 / Math.max(1, totalOps)) + "%");
        System.out.println("Time: " + (elapsed / 1_000_000) + " ms");
        System.out.println("Throughput: " + ((long)numThreads * opsPerThread * 1_000_000_000L / elapsed) + " ops/sec");
        System.out.println("\nKey insight: Under high contention, push+pop cancel each other out");
        System.out.println("without touching shared state. Contention becomes an advantage!");
    }
}
