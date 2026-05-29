import java.util.*;

/**
 * Problem 16: Design Circular Queue
 * 
 * API Contract:
 * - enQueue(value): Insert at rear. Return success.
 * - deQueue(): Delete from front. Return success.
 * - Front(), Rear(): Get front/rear element.
 * - isEmpty(), isFull(): Check state.
 * 
 * Complexity: O(1) for all operations
 * Data Structure: Fixed-size array with head/tail pointers and count
 * 
 * Production Analogy: Network packet buffers, producer-consumer queues,
 * keyboard input buffer, bounded task queues in thread pools
 */
public class Problem16_DesignCircularQueue {

    static class MyCircularQueue {
        private int[] data;
        private int head, tail, size, capacity;

        public MyCircularQueue(int k) {
            data = new int[k];
            capacity = k;
            head = 0; tail = -1; size = 0;
        }

        public boolean enQueue(int value) {
            if (isFull()) return false;
            tail = (tail + 1) % capacity;
            data[tail] = value;
            size++;
            return true;
        }

        public boolean deQueue() {
            if (isEmpty()) return false;
            head = (head + 1) % capacity;
            size--;
            return true;
        }

        public int Front() { return isEmpty() ? -1 : data[head]; }
        public int Rear() { return isEmpty() ? -1 : data[tail]; }
        public boolean isEmpty() { return size == 0; }
        public boolean isFull() { return size == capacity; }
    }

    public static void main(String[] args) {
        MyCircularQueue q = new MyCircularQueue(3);
        assert q.enQueue(1);
        assert q.enQueue(2);
        assert q.enQueue(3);
        assert !q.enQueue(4);
        assert q.Rear() == 3;
        assert q.isFull();
        assert q.deQueue();
        assert q.enQueue(4);
        assert q.Rear() == 4;
        assert q.Front() == 2;

        System.out.println("All tests passed!");
    }
}
