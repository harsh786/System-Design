import java.util.*;

/**
 * Problem 48: Design Circular Buffer (Ring Buffer)
 * 
 * API Contract:
 * - write(val): Write to buffer. Return false if full.
 * - read(): Read oldest value. Return -1 if empty.
 * - isFull(), isEmpty(): Status checks.
 * - overwrite(val): Write even if full (overwrites oldest).
 * 
 * Complexity: O(1) for all operations
 * Data Structure: Fixed array + read/write pointers + count
 * 
 * Production Analogy: Network I/O buffers (TCP receive window), audio streaming buffers,
 * Linux kernel kfifo, logging ring buffers (dmesg), lock-free SPSC queues
 */
public class Problem48_DesignCircularBuffer {

    static class CircularBuffer {
        private int[] buf;
        private int readPtr, writePtr, size, capacity;

        public CircularBuffer(int capacity) {
            this.capacity = capacity;
            buf = new int[capacity];
            readPtr = 0; writePtr = 0; size = 0;
        }

        public boolean write(int val) {
            if (isFull()) return false;
            buf[writePtr] = val;
            writePtr = (writePtr + 1) % capacity;
            size++;
            return true;
        }

        public int read() {
            if (isEmpty()) return -1;
            int val = buf[readPtr];
            readPtr = (readPtr + 1) % capacity;
            size--;
            return val;
        }

        public void overwrite(int val) {
            if (isFull()) readPtr = (readPtr + 1) % capacity; // discard oldest
            else size++;
            buf[writePtr] = val;
            writePtr = (writePtr + 1) % capacity;
        }

        public boolean isFull() { return size == capacity; }
        public boolean isEmpty() { return size == 0; }
    }

    public static void main(String[] args) {
        CircularBuffer cb = new CircularBuffer(3);
        assert cb.write(1);
        assert cb.write(2);
        assert cb.write(3);
        assert !cb.write(4); // full
        assert cb.read() == 1;
        assert cb.write(4); // now has [2,3,4]
        assert cb.read() == 2;

        // Overwrite test
        CircularBuffer cb2 = new CircularBuffer(2);
        cb2.write(1); cb2.write(2);
        cb2.overwrite(3); // overwrites 1
        assert cb2.read() == 2;
        assert cb2.read() == 3;
        assert cb2.isEmpty();

        System.out.println("All tests passed!");
    }
}
