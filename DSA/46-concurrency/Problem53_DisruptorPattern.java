import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.CountDownLatch;

/**
 * Problem 53: Disruptor Pattern (Ring Buffer with Sequence Barriers)
 * 
 * REAL-WORLD USAGE:
 * - LMAX Exchange: processes 6 million orders/sec on a single thread
 * - Log4j2 Async Loggers use Disruptor internally
 * - Apache Storm's internal messaging
 * - Financial trading systems for ultra-low latency event processing
 * 
 * WHY FASTER THAN BlockingQueue:
 * 1. Pre-allocated ring buffer - no GC allocation on hot path
 * 2. Mechanical sympathy - sequential memory access (cache-line friendly)
 * 3. No locks - uses memory barriers via sequence numbers
 * 4. Batching - consumers can process multiple events in one go
 * 5. Single-writer principle eliminates write contention
 * 
 * KEY CONCEPTS:
 * - Sequence: monotonically increasing counter (cursor position)
 * - Ring Buffer: fixed-size array, index = sequence % size
 * - Sequence Barrier: tracks dependencies between producer and consumers
 * - Wait Strategy: how consumers wait (busy-spin, yield, block)
 * 
 * MEMORY ORDERING:
 * - Producer publishes by advancing cursor AFTER writing data (release semantics)
 * - Consumer reads cursor BEFORE reading data (acquire semantics)
 * - AtomicLong with lazySet for producer (StoreStore barrier, not full fence)
 *   provides sufficient ordering with less overhead
 * 
 * PITFALLS:
 * 1. Buffer size MUST be power of 2 (for bitwise AND masking instead of modulo)
 * 2. Single producer assumption - multi-producer needs CAS on claim
 * 3. Slow consumers cause producer to spin-wait (backpressure)
 * 4. False sharing on sequence counters (pad to cache line - 64 bytes)
 */
public class Problem53_DisruptorPattern {

    // ==================== RING BUFFER ====================
    static class RingBuffer<T> {
        private final Object[] buffer;
        private final int mask; // bufferSize - 1 for fast modulo
        private final AtomicLong cursor = new PaddedAtomicLong(-1); // producer sequence
        private final int bufferSize;

        @SuppressWarnings("unchecked")
        RingBuffer(int size) {
            if (Integer.bitCount(size) != 1) {
                throw new IllegalArgumentException("Size must be power of 2");
            }
            this.bufferSize = size;
            this.buffer = new Object[size];
            this.mask = size - 1;
        }

        // Producer: claim next slot
        public long next() {
            return cursor.get() + 1;
        }

        // Producer: write event into slot
        public void set(long sequence, T event) {
            buffer[(int) (sequence & mask)] = event;
        }

        // Producer: publish - makes event visible to consumers
        // Uses lazySet (StoreStore barrier) - cheaper than volatile write
        // Safe because consumer checks cursor BEFORE reading data
        public void publish(long sequence) {
            cursor.lazySet(sequence);
        }

        @SuppressWarnings("unchecked")
        public T get(long sequence) {
            return (T) buffer[(int) (sequence & mask)];
        }

        public long getCursor() {
            return cursor.get();
        }

        public int getBufferSize() {
            return bufferSize;
        }
    }

    // Padded AtomicLong to prevent false sharing (cache line = 64 bytes)
    static class PaddedAtomicLong extends AtomicLong {
        // Padding to fill cache line (AtomicLong is ~16 bytes, pad to 64)
        volatile long p1, p2, p3, p4, p5, p6, p7;

        PaddedAtomicLong(long initialValue) {
            super(initialValue);
        }

        // Prevent JVM from optimizing away padding
        public long preventOptimization() {
            return p1 + p2 + p3 + p4 + p5 + p6 + p7;
        }
    }

    // ==================== SEQUENCE BARRIER ====================
    // Consumer uses this to wait for producer to advance
    static class SequenceBarrier {
        private final AtomicLong producerCursor;
        private final AtomicLong consumerSequence;

        SequenceBarrier(AtomicLong producerCursor) {
            this.producerCursor = producerCursor;
            this.consumerSequence = new PaddedAtomicLong(-1);
        }

        // Wait for sequence to be available (busy-spin strategy)
        public long waitFor(long sequence) {
            while (producerCursor.get() < sequence) {
                Thread.onSpinWait(); // JDK9+ hint to CPU (reduces power, allows hyperthreading)
            }
            return producerCursor.get();
        }

        public void setConsumerSequence(long seq) {
            consumerSequence.lazySet(seq);
        }

        public long getConsumerSequence() {
            return consumerSequence.get();
        }
    }

    // ==================== SINGLE PRODUCER ====================
    static class Producer implements Runnable {
        private final RingBuffer<Long> ringBuffer;
        private final SequenceBarrier consumerBarrier; // to check consumer hasn't fallen behind
        private final int numEvents;

        Producer(RingBuffer<Long> ringBuffer, SequenceBarrier consumerBarrier, int numEvents) {
            this.ringBuffer = ringBuffer;
            this.consumerBarrier = consumerBarrier;
            this.numEvents = numEvents;
        }

        @Override
        public void run() {
            for (long i = 0; i < numEvents; i++) {
                long seq = i;
                // Backpressure: wait if buffer is full
                // Buffer is full when producer is bufferSize ahead of consumer
                while (seq - consumerBarrier.getConsumerSequence() >= ringBuffer.getBufferSize()) {
                    Thread.onSpinWait();
                }
                ringBuffer.set(seq, i);
                ringBuffer.publish(seq); // Makes data visible (memory barrier)
            }
        }
    }

    // ==================== CONSUMER (Event Handler) ====================
    static class Consumer implements Runnable {
        private final RingBuffer<Long> ringBuffer;
        private final SequenceBarrier barrier;
        private final int numEvents;
        private long sum = 0;

        Consumer(RingBuffer<Long> ringBuffer, SequenceBarrier barrier, int numEvents) {
            this.ringBuffer = ringBuffer;
            this.barrier = barrier;
            this.numEvents = numEvents;
        }

        @Override
        public void run() {
            long nextSequence = 0;
            while (nextSequence < numEvents) {
                long available = barrier.waitFor(nextSequence);
                // BATCH processing: process all available events at once
                while (nextSequence <= available) {
                    Long event = ringBuffer.get(nextSequence);
                    sum += event;
                    nextSequence++;
                }
                // Update consumer position (allows producer to overwrite old slots)
                barrier.setConsumerSequence(nextSequence - 1);
            }
        }

        public long getSum() { return sum; }
    }

    // ==================== STRESS TEST ====================
    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Disruptor Pattern (Ring Buffer) Stress Test ===\n");

        int bufferSize = 1024 * 64; // 64K entries, must be power of 2
        int numEvents = 10_000_000;

        RingBuffer<Long> ringBuffer = new RingBuffer<>(bufferSize);
        SequenceBarrier consumerBarrier = new SequenceBarrier(ringBuffer.cursor);
        SequenceBarrier producerBarrier = new SequenceBarrier(ringBuffer.cursor);

        Consumer consumer = new Consumer(ringBuffer, producerBarrier, numEvents);
        Producer producer = new Producer(ringBuffer, consumerBarrier, numEvents);

        Thread consumerThread = new Thread(consumer, "Consumer");
        Thread producerThread = new Thread(producer, "Producer");

        long start = System.nanoTime();
        consumerThread.start();
        producerThread.start();

        producerThread.join();
        consumerThread.join();
        long elapsed = System.nanoTime() - start;

        // Verify: sum of 0..N-1 = N*(N-1)/2
        long expectedSum = (long) numEvents * (numEvents - 1) / 2;
        System.out.println("Events processed: " + numEvents);
        System.out.println("Expected sum: " + expectedSum);
        System.out.println("Actual sum:   " + consumer.getSum());
        System.out.println("Correct: " + (expectedSum == consumer.getSum()));
        System.out.println("Time: " + (elapsed / 1_000_000) + " ms");
        System.out.println("Throughput: " + (numEvents * 1_000_000_000L / elapsed) + " events/sec");
        System.out.println("\nKey insight: No locks, no allocation on hot path, cache-friendly sequential access");
    }
}
