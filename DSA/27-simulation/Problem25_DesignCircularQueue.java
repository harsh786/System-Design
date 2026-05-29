/**
 * Problem: Design Circular Queue (LeetCode 622)
 * Approach: Array-based circular buffer with head/tail pointers
 * Complexity: O(1) all operations
 * Production Analogy: Ring buffer for producer-consumer patterns in I/O systems
 */
public class Problem25_DesignCircularQueue {
    int[] data; int head = 0, count = 0, capacity;
    public Problem25_DesignCircularQueue(int k) { data = new int[k]; capacity = k; }
    public boolean enQueue(int value) {
        if (isFull()) return false;
        data[(head+count)%capacity] = value; count++; return true;
    }
    public boolean deQueue() { if (isEmpty()) return false; head=(head+1)%capacity; count--; return true; }
    public int Front() { return isEmpty() ? -1 : data[head]; }
    public int Rear() { return isEmpty() ? -1 : data[(head+count-1)%capacity]; }
    public boolean isEmpty() { return count==0; }
    public boolean isFull() { return count==capacity; }
    public static void main(String[] args) {
        Problem25_DesignCircularQueue q = new Problem25_DesignCircularQueue(3);
        System.out.println(q.enQueue(1)); // true
        System.out.println(q.enQueue(2)); // true
        System.out.println(q.enQueue(3)); // true
        System.out.println(q.enQueue(4)); // false
        System.out.println(q.Rear());     // 3
    }
}
