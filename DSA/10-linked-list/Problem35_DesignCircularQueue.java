/**
 * Problem 35: Design Circular Queue
 * 
 * Approach: Array-based circular buffer with front/rear pointers.
 * Time Complexity: O(1) for all operations
 * Space Complexity: O(k)
 * 
 * Production Analogy: Ring buffer for high-throughput logging (like LMAX Disruptor)
 * where producers and consumers share a fixed-size circular buffer.
 */
public class Problem35_DesignCircularQueue {
    static class MyCircularQueue {
        int[] data;
        int front, rear, size, capacity;

        public MyCircularQueue(int k) { data = new int[k]; capacity = k; front = 0; rear = -1; }

        public boolean enQueue(int value) {
            if (isFull()) return false;
            rear = (rear + 1) % capacity;
            data[rear] = value;
            size++; return true;
        }

        public boolean deQueue() {
            if (isEmpty()) return false;
            front = (front + 1) % capacity;
            size--; return true;
        }

        public int Front() { return isEmpty() ? -1 : data[front]; }
        public int Rear() { return isEmpty() ? -1 : data[rear]; }
        public boolean isEmpty() { return size == 0; }
        public boolean isFull() { return size == capacity; }
    }

    public static void main(String[] args) {
        MyCircularQueue q = new MyCircularQueue(3);
        System.out.println(q.enQueue(1)); // true
        System.out.println(q.enQueue(2)); // true
        System.out.println(q.enQueue(3)); // true
        System.out.println(q.enQueue(4)); // false
        System.out.println(q.Rear());     // 3
        System.out.println(q.isFull());   // true
        System.out.println(q.deQueue());  // true
        System.out.println(q.enQueue(4)); // true
        System.out.println(q.Rear());     // 4
    }
}
