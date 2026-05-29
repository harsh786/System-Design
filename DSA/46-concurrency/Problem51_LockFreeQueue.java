import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Problem 51: Lock-Free Queue (Michael-Scott Algorithm Concept)
 * 
 * REAL-WORLD USAGE:
 * - Java's ConcurrentLinkedQueue is based on this algorithm
 * - Used in message passing systems (Kafka internal buffers, Netty event loops)
 * - Actor mailboxes in Akka/Erlang-style systems
 * 
 * KEY CONCEPTS:
 * - Lock-free: At least one thread makes progress (no deadlock possible)
 * - Uses CAS (Compare-And-Swap) for atomic pointer updates
 * - Sentinel/dummy node avoids special cases for empty queue
 * 
 * MEMORY ORDERING:
 * - AtomicReference provides sequential consistency by default in Java
 * - compareAndSet is a full memory fence (happens-before relationship)
 * - Ensures visibility: if CAS succeeds, all prior writes are visible
 * 
 * PITFALLS:
 * 1. ABA problem on dequeue (mitigated here by GC - Java reclaims nodes)
 * 2. Helping mechanism is critical: if a thread dies mid-enqueue, others must
 *    advance the tail pointer (lazy tail update)
 * 3. Without the dummy node, you'd need complex empty-queue handling
 */
public class Problem51_LockFreeQueue<T> {

    private static class Node<T> {
        final T value;
        final AtomicReference<Node<T>> next;

        Node(T value) {
            this.value = value;
            this.next = new AtomicReference<>(null);
        }
    }

    // Head always points to a dummy/sentinel node; real data starts at head.next
    private final AtomicReference<Node<T>> head;
    // Tail may lag behind the actual last node (lazy update)
    private final AtomicReference<Node<T>> tail;

    public Problem51_LockFreeQueue() {
        Node<T> sentinel = new Node<>(null);
        head = new AtomicReference<>(sentinel);
        tail = new AtomicReference<>(sentinel);
    }

    /**
     * Enqueue: Append to the end of the linked list.
     * 
     * Two-step process:
     * 1. CAS the next pointer of the current last node to the new node
     * 2. CAS the tail pointer to the new node (may be done by another thread - "helping")
     * 
     * If step 2 fails, it means another thread already advanced tail - that's fine.
     */
    public void enqueue(T value) {
        Node<T> newNode = new Node<>(value);
        while (true) {
            Node<T> curTail = tail.get();
            Node<T> next = curTail.next.get();

            // Check if tail is still consistent
            if (curTail == tail.get()) {
                if (next == null) {
                    // Tail is pointing to the last node - try to link new node
                    if (curTail.next.compareAndSet(null, newNode)) {
                        // Successfully linked; try to advance tail (best-effort)
                        tail.compareAndSet(curTail, newNode);
                        return;
                    }
                } else {
                    // Tail is lagging - help advance it (HELPING mechanism)
                    // This is what makes the algorithm lock-free rather than just non-blocking
                    tail.compareAndSet(curTail, next);
                }
            }
        }
    }

    /**
     * Dequeue: Remove from the front (after the sentinel node).
     * 
     * Returns null if queue is empty.
     * After successful dequeue, the old first data node becomes the new sentinel.
     */
    public T dequeue() {
        while (true) {
            Node<T> curHead = head.get();
            Node<T> curTail = tail.get();
            Node<T> next = curHead.next.get();

            if (curHead == head.get()) {
                if (curHead == curTail) {
                    // Queue appears empty or tail is lagging
                    if (next == null) {
                        return null; // Queue is truly empty
                    }
                    // Tail lagging behind; help advance
                    tail.compareAndSet(curTail, next);
                } else {
                    // Read value before CAS, because after CAS another dequeue could free the node
                    T value = next.value;
                    if (head.compareAndSet(curHead, next)) {
                        // next becomes new sentinel; old sentinel is garbage collected
                        return value;
                    }
                }
            }
        }
    }

    public boolean isEmpty() {
        return head.get().next.get() == null;
    }

    // ==================== STRESS TEST ====================
    public static void main(String[] args) throws InterruptedException {
        Problem51_LockFreeQueue<Integer> queue = new Problem51_LockFreeQueue<>();
        int numProducers = 4;
        int numConsumers = 4;
        int itemsPerProducer = 250_000;
        AtomicInteger produced = new AtomicInteger(0);
        AtomicInteger consumed = new AtomicInteger(0);
        AtomicInteger sumProduced = new AtomicInteger(0);
        AtomicInteger sumConsumed = new AtomicInteger(0);

        CountDownLatch startLatch = new CountDownLatch(1);
        CountDownLatch doneLatch = new CountDownLatch(numProducers + numConsumers);

        // Producers
        for (int p = 0; p < numProducers; p++) {
            final int pid = p;
            new Thread(() -> {
                try { startLatch.await(); } catch (InterruptedException e) { return; }
                for (int i = 0; i < itemsPerProducer; i++) {
                    int val = pid * itemsPerProducer + i;
                    queue.enqueue(val);
                    produced.incrementAndGet();
                    sumProduced.addAndGet(val);
                }
                doneLatch.countDown();
            }).start();
        }

        // Consumers
        int totalItems = numProducers * itemsPerProducer;
        for (int c = 0; c < numConsumers; c++) {
            new Thread(() -> {
                try { startLatch.await(); } catch (InterruptedException e) { return; }
                while (consumed.get() < totalItems) {
                    Integer val = queue.dequeue();
                    if (val != null) {
                        consumed.incrementAndGet();
                        sumConsumed.addAndGet(val);
                    }
                }
                doneLatch.countDown();
            }).start();
        }

        long start = System.nanoTime();
        startLatch.countDown();
        doneLatch.await();
        long elapsed = System.nanoTime() - start;

        System.out.println("=== Lock-Free Queue (Michael-Scott) Stress Test ===");
        System.out.println("Producers: " + numProducers + ", Consumers: " + numConsumers);
        System.out.println("Total items: " + totalItems);
        System.out.println("Produced: " + produced.get() + ", Consumed: " + consumed.get());
        System.out.println("Sum check - Produced: " + sumProduced.get() + ", Consumed: " + sumConsumed.get());
        System.out.println("Sums match: " + (sumProduced.get() == sumConsumed.get()));
        System.out.println("Time: " + (elapsed / 1_000_000) + " ms");
        System.out.println("Throughput: " + (totalItems * 1000L / (elapsed / 1_000_000)) + " ops/sec");
    }
}
