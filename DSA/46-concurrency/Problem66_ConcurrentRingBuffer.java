import java.util.concurrent.atomic.*;
import java.util.concurrent.*;

/**
 * Problem 66: Concurrent Ring Buffer (SPSC and MPMC)
 * 
 * REAL-WORLD USAGE:
 * - Network packet buffers (NIC ring buffers, DPDK)
 * - Audio/video streaming buffers
 * - Kernel I/O: io_uring (Linux async I/O)
 * - Inter-thread communication in real-time systems
 * - Log buffers (circular logging)
 * 
 * TWO VARIANTS:
 * 1. SPSC (Single Producer Single Consumer): simplest, fastest
 *    - Only needs memory barriers, no CAS
 *    - Used for dedicated producer-consumer pairs
 * 
 * 2. MPMC (Multi Producer Multi Consumer): general purpose
 *    - Needs CAS for both enqueue and dequeue
 *    - Used when multiple threads share a buffer
 * 
 * MEMORY ORDERING:
 * - SPSC: producer updates write index with release; consumer reads with acquire
 * - MPMC: CAS provides sequential consistency at claim points
 * - Data writes must be visible BEFORE index advancement (release)
 * - Index must be read BEFORE data (acquire)
 * 
 * PITFALLS:
 * 1. Size MUST be power of 2 (bitwise AND for fast modulo)
 * 2. Full/empty disambiguation: use separate read/write counters (not pointers)
 * 3. False sharing: pad head and tail to different cache lines
 * 4. MPMC: must handle the gap between claiming a slot and filling it
 */
public class Problem66_ConcurrentRingBuffer {

    // ==================== SPSC RING BUFFER ====================
    static class SPSCRingBuffer<T> {
        private final Object[] buffer;
        private final int mask;
        // Padded to avoid false sharing between producer and consumer
        private volatile long writeIndex = 0; // Only written by producer
        private volatile long readIndex = 0;  // Only written by consumer

        SPSCRingBuffer(int capacity) {
            if (Integer.bitCount(capacity) != 1)
                throw new IllegalArgumentException("Capacity must be power of 2");
            this.buffer = new Object[capacity];
            this.mask = capacity - 1;
        }

        /** Producer: returns false if full */
        public boolean offer(T item) {
            long wIdx = writeIndex;
            if (wIdx - readIndex >= buffer.length) {
                return false; // Full
            }
            buffer[(int)(wIdx & mask)] = item;
            // Release: ensure item is written before index update is visible
            writeIndex = wIdx + 1; // Volatile write = release fence
            return true;
        }

        /** Consumer: returns null if empty */
        @SuppressWarnings("unchecked")
        public T poll() {
            long rIdx = readIndex;
            if (rIdx >= writeIndex) {
                return null; // Empty
            }
            // Acquire: volatile read of writeIndex above ensures we see the data
            T item = (T) buffer[(int)(rIdx & mask)];
            readIndex = rIdx + 1; // Release
            return item;
        }

        public int size() { return (int)(writeIndex - readIndex); }
    }

    // ==================== MPMC RING BUFFER ====================
    static class MPMCRingBuffer<T> {
        private final Object[] buffer;
        private final long[] sequences; // Per-slot sequence numbers
        private final int mask;
        private final AtomicLong head = new AtomicLong(0); // Next slot to dequeue
        private final AtomicLong tail = new AtomicLong(0); // Next slot to enqueue

        MPMCRingBuffer(int capacity) {
            if (Integer.bitCount(capacity) != 1)
                throw new IllegalArgumentException("Capacity must be power of 2");
            this.buffer = new Object[capacity];
            this.sequences = new long[capacity];
            this.mask = capacity - 1;
            // Initialize sequences: slot i expects sequence i
            for (int i = 0; i < capacity; i++) {
                sequences[i] = i;
            }
        }

        /**
         * Enqueue: Multiple producers can call concurrently.
         * Uses CAS to claim a slot, then writes data, then publishes.
         */
        public boolean offer(T item) {
            long pos;
            while (true) {
                pos = tail.get();
                int idx = (int)(pos & mask);
                long seq = sequences[idx]; // Volatile read (array of longs, not atomic - simplified)

                if (seq == pos) {
                    // Slot is available for writing
                    if (tail.compareAndSet(pos, pos + 1)) {
                        break; // Claimed this slot
                    }
                } else if (seq < pos) {
                    return false; // Buffer full
                }
                // seq > pos means another producer claimed but hasn't published yet - retry
                Thread.onSpinWait();
            }

            // Write data into claimed slot
            int idx = (int)(pos & mask);
            buffer[idx] = item;
            // Publish: advance sequence to signal consumers this slot is ready
            sequences[idx] = pos + 1;
            return true;
        }

        /**
         * Dequeue: Multiple consumers can call concurrently.
         */
        @SuppressWarnings("unchecked")
        public T poll() {
            long pos;
            while (true) {
                pos = head.get();
                int idx = (int)(pos & mask);
                long seq = sequences[idx];

                if (seq == pos + 1) {
                    // Slot has been published (data is ready)
                    if (head.compareAndSet(pos, pos + 1)) {
                        break; // Claimed this slot for reading
                    }
                } else if (seq <= pos) {
                    return null; // Buffer empty or not yet published
                }
                Thread.onSpinWait();
            }

            int idx = (int)(pos & mask);
            T item = (T) buffer[idx];
            buffer[idx] = null; // Help GC
            // Publish: advance sequence to signal producers this slot is free
            sequences[idx] = pos + mask + 1;
            return item;
        }

        public int size() { return (int)(tail.get() - head.get()); }
    }

    // ==================== STRESS TEST ====================
    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Concurrent Ring Buffer (SPSC & MPMC) ===\n");

        // Test 1: SPSC
        System.out.println("--- SPSC Ring Buffer ---");
        SPSCRingBuffer<Long> spsc = new SPSCRingBuffer<>(65536);
        int numItems = 10_000_000;
        AtomicLong spscSum = new AtomicLong(0);

        Thread producer = new Thread(() -> {
            for (long i = 0; i < numItems; i++) {
                while (!spsc.offer(i)) Thread.onSpinWait();
            }
        });
        Thread consumer = new Thread(() -> {
            long count = 0;
            while (count < numItems) {
                Long val = spsc.poll();
                if (val != null) { spscSum.addAndGet(val); count++; }
                else Thread.onSpinWait();
            }
        });

        long start = System.nanoTime();
        producer.start(); consumer.start();
        producer.join(); consumer.join();
        long elapsed = System.nanoTime() - start;

        long expectedSum = (long)numItems * (numItems - 1) / 2;
        System.out.println("Items: " + numItems);
        System.out.println("Sum correct: " + (spscSum.get() == expectedSum));
        System.out.println("Time: " + (elapsed / 1_000_000) + " ms");
        System.out.println("Throughput: " + (numItems * 1_000_000_000L / elapsed) + " ops/sec");

        // Test 2: MPMC
        System.out.println("\n--- MPMC Ring Buffer ---");
        MPMCRingBuffer<Integer> mpmc = new MPMCRingBuffer<>(65536);
        int numProducers = 4, numConsumers = 4;
        int itemsPerProducer = 1_000_000;
        AtomicInteger produced = new AtomicInteger(0);
        AtomicInteger consumed = new AtomicInteger(0);
        CountDownLatch done = new CountDownLatch(numProducers + numConsumers);
        CountDownLatch startLatch = new CountDownLatch(1);
        int totalItems = numProducers * itemsPerProducer;

        for (int p = 0; p < numProducers; p++) {
            new Thread(() -> {
                try { startLatch.await(); } catch (InterruptedException e) { return; }
                for (int i = 0; i < itemsPerProducer; i++) {
                    while (!mpmc.offer(i)) Thread.onSpinWait();
                    produced.incrementAndGet();
                }
                done.countDown();
            }).start();
        }
        for (int c = 0; c < numConsumers; c++) {
            new Thread(() -> {
                try { startLatch.await(); } catch (InterruptedException e) { return; }
                while (consumed.get() < totalItems) {
                    if (mpmc.poll() != null) consumed.incrementAndGet();
                    else Thread.onSpinWait();
                }
                done.countDown();
            }).start();
        }

        start = System.nanoTime();
        startLatch.countDown();
        done.await();
        elapsed = System.nanoTime() - start;

        System.out.println("Producers: " + numProducers + ", Consumers: " + numConsumers);
        System.out.println("Total items: " + totalItems);
        System.out.println("Produced: " + produced.get() + ", Consumed: " + consumed.get());
        System.out.println("Time: " + (elapsed / 1_000_000) + " ms");
        System.out.println("Throughput: " + (totalItems * 1_000_000_000L / elapsed) + " ops/sec");
        System.out.println("\nKey insight: SPSC is ~10x faster than MPMC (no CAS needed).");
        System.out.println("io_uring, NIC ring buffers, and audio systems use SPSC for this reason.");
    }
}
