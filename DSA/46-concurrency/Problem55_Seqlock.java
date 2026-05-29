import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.CountDownLatch;

/**
 * Problem 55: Seqlock (Sequence Lock for Read-Heavy Workloads)
 * 
 * REAL-WORLD USAGE:
 * - Linux kernel: xtime (system clock), jiffies
 * - Network packet timestamps
 * - Reading hardware counters (CPU performance monitors)
 * - Any data that's small enough to be read quickly but updated frequently
 * 
 * HOW IT WORKS:
 * - A sequence counter (even = stable, odd = write in progress)
 * - Writer: increment seq to odd → write data → increment seq to even
 * - Reader: read seq (must be even) → read data → read seq again → if same, data is consistent
 * - If reader detects seq changed or was odd, RETRY the read
 * 
 * VS RWLOCK:
 * - Seqlock: writer never blocks; reader may retry (writer-priority)
 * - RWLock: writer blocks if readers are active (reader-priority)
 * - Seqlock is better when writes are short and data is small
 * 
 * MEMORY ORDERING:
 * - Writer: the sequence increment BEFORE write acts as release fence
 *   The sequence increment AFTER write acts as release fence
 * - Reader: first seq read needs acquire semantics
 *   Second seq read needs acquire semantics + compiler barrier
 * - In Java, volatile (AtomicInteger) provides these barriers
 * 
 * PITFALLS:
 * 1. ONLY works for data that can be read atomically or re-read safely
 *    (reader must not follow pointers that might be freed by writer)
 * 2. Writer starvation of readers is possible (constant writes = infinite retries)
 * 3. Not suitable for large data structures (read takes too long, likely to conflict)
 * 4. Must not use for data containing pointers/references in non-GC languages
 */
public class Problem55_Seqlock {

    // ==================== SEQLOCK IMPLEMENTATION ====================
    static class SeqLock {
        // Sequence counter: even = consistent, odd = write in progress
        // Volatile (via AtomicInteger) ensures memory ordering
        private final AtomicInteger sequence = new AtomicInteger(0);

        public int readBegin() {
            int seq;
            do {
                seq = sequence.get();
                // Spin while writer is active (odd sequence)
            } while ((seq & 1) != 0);
            // seq is even - data should be consistent
            // The volatile read of sequence acts as an acquire barrier
            return seq;
        }

        public boolean readRetry(int startSeq) {
            // Need to prevent reordering of data reads with this check
            // AtomicInteger.get() provides acquire semantics
            return sequence.get() != startSeq;
        }

        public void writeLock() {
            // Increment sequence to odd (signals write in progress)
            // In multi-writer scenario, you'd need a real lock here
            int seq = sequence.get();
            sequence.set(seq + 1);
            // After this volatile write, subsequent data writes are ordered after it
        }

        public void writeUnlock() {
            // Increment sequence to even (signals write complete)
            int seq = sequence.get();
            sequence.set(seq + 1);
            // This volatile write ensures all data writes are visible before sequence update
        }
    }

    // ==================== PROTECTED DATA: Coordinate (multi-field) ====================
    /**
     * Represents a 3D coordinate that must be read consistently.
     * Without seqlock, reader could see x from old write and y from new write (torn read).
     */
    static class SeqlockCoordinate {
        private final SeqLock seqLock = new SeqLock();
        // These are NOT volatile - seqlock provides the ordering guarantees
        // (In practice with Java memory model, we rely on the volatile seq reads
        //  to establish happens-before; the fields could be read stale without it)
        private volatile double x, y, z;
        private volatile long timestamp;

        public void update(double x, double y, double z) {
            seqLock.writeLock();
            // --- Critical section: data is inconsistent here ---
            this.x = x;
            this.y = y;
            this.z = z;
            this.timestamp = System.nanoTime();
            // --- End critical section ---
            seqLock.writeUnlock();
        }

        public double[] read() {
            double rx, ry, rz;
            long rts;
            int seq;
            do {
                seq = seqLock.readBegin();
                // Read all fields (may be inconsistent if writer is active)
                rx = this.x;
                ry = this.y;
                rz = this.z;
                rts = this.timestamp;
            } while (seqLock.readRetry(seq));
            // If we reach here, all reads are consistent
            return new double[]{rx, ry, rz, rts};
        }
    }

    // ==================== PROTECTED DATA: System Clock ====================
    static class SeqlockClock {
        private final SeqLock seqLock = new SeqLock();
        private volatile long seconds;
        private volatile long nanoseconds;

        public void tick(long secs, long nanos) {
            seqLock.writeLock();
            this.seconds = secs;
            this.nanoseconds = nanos;
            seqLock.writeUnlock();
        }

        public long[] readTime() {
            long s, ns;
            int seq;
            do {
                seq = seqLock.readBegin();
                s = seconds;
                ns = nanoseconds;
            } while (seqLock.readRetry(seq));
            return new long[]{s, ns};
        }
    }

    // ==================== STRESS TEST ====================
    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Seqlock Stress Test ===\n");

        SeqlockCoordinate coord = new SeqlockCoordinate();
        int numReaders = 6;
        int numWriters = 2;
        int readsPerThread = 5_000_000;
        int writesPerThread = 1_000_000;
        AtomicInteger totalReads = new AtomicInteger(0);
        AtomicInteger retries = new AtomicInteger(0);
        AtomicInteger inconsistencies = new AtomicInteger(0);
        CountDownLatch startLatch = new CountDownLatch(1);
        CountDownLatch doneLatch = new CountDownLatch(numReaders + numWriters);

        // Writers: update coordinates
        for (int w = 0; w < numWriters; w++) {
            final int wid = w;
            new Thread(() -> {
                try { startLatch.await(); } catch (InterruptedException e) { return; }
                for (int i = 0; i < writesPerThread; i++) {
                    // Writer sets x=y=z to same value (for consistency check)
                    double val = wid * 1_000_000.0 + i;
                    coord.update(val, val, val);
                }
                doneLatch.countDown();
            }).start();
        }

        // Readers: read and verify consistency
        for (int r = 0; r < numReaders; r++) {
            new Thread(() -> {
                try { startLatch.await(); } catch (InterruptedException e) { return; }
                for (int i = 0; i < readsPerThread; i++) {
                    double[] result = coord.read();
                    totalReads.incrementAndGet();
                    // Consistency check: x, y, z should all be equal
                    if (result[0] != result[1] || result[1] != result[2]) {
                        inconsistencies.incrementAndGet();
                    }
                }
                doneLatch.countDown();
            }).start();
        }

        long start = System.nanoTime();
        startLatch.countDown();
        doneLatch.await();
        long elapsed = System.nanoTime() - start;

        System.out.println("Readers: " + numReaders + " (" + readsPerThread + " reads each)");
        System.out.println("Writers: " + numWriters + " (" + writesPerThread + " writes each)");
        System.out.println("Total reads completed: " + totalReads.get());
        System.out.println("Inconsistencies detected: " + inconsistencies.get());
        System.out.println("Time: " + (elapsed / 1_000_000) + " ms");
        System.out.println("Read throughput: " + (totalReads.get() * 1_000_000_000L / elapsed) + " reads/sec");
        System.out.println("\nKey insight: Writers NEVER block. Readers retry on conflict.");
        System.out.println("Perfect for system clocks, counters, small frequently-updated state.");
    }
}
