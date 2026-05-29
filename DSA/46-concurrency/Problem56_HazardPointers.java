import java.util.concurrent.atomic.*;
import java.util.concurrent.*;
import java.util.*;

/**
 * Problem 56: Hazard Pointers for Memory Reclamation
 * 
 * REAL-WORLD USAGE:
 * - Folly (Facebook's C++ library) uses hazard pointers extensively
 * - Lock-free data structures in non-GC languages (C, C++, Rust)
 * - Java's direct memory / off-heap buffer management
 * - Database buffer pool page eviction (protect pages being read)
 * 
 * THE PROBLEM:
 * In lock-free structures, when can you safely free/reclaim a removed node?
 * - Thread A removes node X from the list
 * - Thread B might still be reading node X (got pointer before removal)
 * - If A frees X, B reads garbage → use-after-free
 * 
 * SOLUTION - HAZARD POINTERS:
 * - Each thread publishes pointers it's currently accessing ("hazard pointers")
 * - Before freeing a node, check all threads' hazard pointers
 * - If ANY thread has a hazard pointer to the node, defer the free
 * - Periodically scan and free deferred nodes that are no longer hazardous
 * 
 * MEMORY ORDERING:
 * - Publishing a hazard pointer must use release semantics (visible to reclaimers)
 * - Reading hazard pointers during scan must use acquire semantics
 * - The "announce-then-validate" pattern:
 *   1. Set hazard pointer to node (store-release)
 *   2. Re-read the source pointer to confirm node is still accessible
 *   If source changed, our hazard pointer protects a stale node - clear it
 * 
 * PITFALLS:
 * 1. Must clear hazard pointer after use (memory leak if forgotten)
 * 2. Number of hazard pointers per thread is fixed (typically 1-2)
 * 3. Deferred free list grows unbounded if reclamation is slow
 * 4. In Java, this pattern is less common (GC handles it) but useful for
 *    off-heap memory, file handles, or connection objects
 */
public class Problem56_HazardPointers {

    static final int MAX_THREADS = 16;
    static final int HAZARD_POINTERS_PER_THREAD = 2;

    // ==================== HAZARD POINTER REGISTRY ====================
    static class HazardPointerRegistry<T> {
        // Published hazard pointers - visible to all threads
        @SuppressWarnings("unchecked")
        private final AtomicReference<T>[] hazardPointers = new AtomicReference[MAX_THREADS * HAZARD_POINTERS_PER_THREAD];
        // Retired nodes waiting to be reclaimed
        private final ConcurrentLinkedQueue<T> retiredList = new ConcurrentLinkedQueue<>();
        private final AtomicInteger retiredCount = new AtomicInteger(0);
        private static final int SCAN_THRESHOLD = 32; // Trigger scan when this many retired

        HazardPointerRegistry() {
            for (int i = 0; i < hazardPointers.length; i++) {
                hazardPointers[i] = new AtomicReference<>(null);
            }
        }

        /**
         * Protect: Announce that current thread is accessing this node.
         * Must use the "announce-then-validate" pattern.
         */
        public void protect(int threadId, int slot, T node) {
            int idx = threadId * HAZARD_POINTERS_PER_THREAD + slot;
            hazardPointers[idx].set(node); // Release semantics via volatile write
        }

        /**
         * Clear: Thread is done accessing the node.
         */
        public void clear(int threadId, int slot) {
            int idx = threadId * HAZARD_POINTERS_PER_THREAD + slot;
            hazardPointers[idx].set(null);
        }

        /**
         * Retire: Node has been removed from the data structure.
         * Don't free immediately - it might still be accessed.
         */
        public void retire(T node) {
            retiredList.add(node);
            if (retiredCount.incrementAndGet() >= SCAN_THRESHOLD) {
                scan();
            }
        }

        /**
         * Scan: Check which retired nodes are safe to reclaim.
         * A node is safe if NO thread has a hazard pointer to it.
         */
        public int scan() {
            // Collect all active hazard pointers
            Set<T> protected_nodes = new HashSet<>();
            for (AtomicReference<T> hp : hazardPointers) {
                T node = hp.get(); // Acquire semantics via volatile read
                if (node != null) {
                    protected_nodes.add(node);
                }
            }

            // Check each retired node
            int reclaimed = 0;
            Iterator<T> it = retiredList.iterator();
            while (it.hasNext()) {
                T node = it.next();
                if (!protected_nodes.contains(node)) {
                    it.remove();
                    retiredCount.decrementAndGet();
                    reclaimed++;
                    // In C++: actually free the memory here
                    // In Java: let GC handle it, or return to pool
                }
            }
            return reclaimed;
        }

        public int getRetiredCount() {
            return retiredCount.get();
        }
    }

    // ==================== LOCK-FREE STACK WITH HAZARD POINTERS ====================
    static class Node<T> {
        final T value;
        volatile Node<T> next;
        Node(T value) { this.value = value; }
    }

    static class SafeStack<T> {
        private final AtomicReference<Node<T>> top = new AtomicReference<>(null);
        private final HazardPointerRegistry<Node<T>> hpRegistry = new HazardPointerRegistry<>();
        private final AtomicInteger threadIdCounter = new AtomicInteger(0);
        private final ThreadLocal<Integer> threadId = ThreadLocal.withInitial(() -> threadIdCounter.getAndIncrement());

        public void push(T value) {
            Node<T> newNode = new Node<>(value);
            while (true) {
                Node<T> curTop = top.get();
                newNode.next = curTop;
                if (top.compareAndSet(curTop, newNode)) return;
            }
        }

        public T pop() {
            int tid = threadId.get();
            while (true) {
                Node<T> curTop = top.get();
                if (curTop == null) return null;

                // PROTECT: announce we're reading curTop
                hpRegistry.protect(tid, 0, curTop);

                // VALIDATE: check if top still points to curTop
                // (if not, our hazard pointer protects a stale node)
                if (top.get() != curTop) {
                    hpRegistry.clear(tid, 0);
                    continue; // Retry
                }

                // Safe to read curTop.next (node is protected)
                Node<T> next = curTop.next;
                if (top.compareAndSet(curTop, next)) {
                    T value = curTop.value;
                    // Clear hazard pointer BEFORE retiring
                    hpRegistry.clear(tid, 0);
                    // RETIRE: don't free yet, let registry handle it
                    hpRegistry.retire(curTop);
                    return value;
                }
                hpRegistry.clear(tid, 0);
            }
        }

        public int forceReclaim() {
            return hpRegistry.scan();
        }

        public int getRetiredCount() {
            return hpRegistry.getRetiredCount();
        }
    }

    // ==================== STRESS TEST ====================
    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Hazard Pointers for Memory Reclamation ===\n");

        SafeStack<Integer> stack = new SafeStack<>();
        int numThreads = 8;
        int opsPerThread = 500_000;
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

        int finalReclaimed = stack.forceReclaim();

        System.out.println("Threads: " + numThreads + ", Ops/thread: " + opsPerThread);
        System.out.println("Pushes: " + pushCount.get() + ", Pops: " + popCount.get());
        System.out.println("Retired nodes pending: " + stack.getRetiredCount());
        System.out.println("Final reclamation sweep: " + finalReclaimed + " nodes freed");
        System.out.println("Time: " + (elapsed / 1_000_000) + " ms");
        System.out.println("\nKey insight: Hazard pointers let lock-free structures safely reclaim memory");
        System.out.println("without GC. Critical in C++ (Folly), useful in Java for off-heap resources.");
    }
}
