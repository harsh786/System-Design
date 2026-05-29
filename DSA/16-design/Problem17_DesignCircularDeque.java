import java.util.*;

/**
 * Problem 17: Design Circular Deque
 * 
 * API Contract: Insert/delete from front and rear, get front/rear, isEmpty/isFull
 * Complexity: O(1) for all operations
 * Data Structure: Circular array with front/rear pointers
 * 
 * Production Analogy: Work-stealing queues in thread pools,
 * sliding window implementations, double-ended priority scheduling
 */
public class Problem17_DesignCircularDeque {

    static class MyCircularDeque {
        private int[] data;
        private int front, rear, size, cap;

        public MyCircularDeque(int k) {
            data = new int[k];
            cap = k; front = 0; rear = k - 1; size = 0;
        }

        public boolean insertFront(int value) {
            if (isFull()) return false;
            front = (front - 1 + cap) % cap;
            data[front] = value;
            size++;
            return true;
        }

        public boolean insertLast(int value) {
            if (isFull()) return false;
            rear = (rear + 1) % cap;
            data[rear] = value;
            size++;
            return true;
        }

        public boolean deleteFront() {
            if (isEmpty()) return false;
            front = (front + 1) % cap;
            size--;
            return true;
        }

        public boolean deleteLast() {
            if (isEmpty()) return false;
            rear = (rear - 1 + cap) % cap;
            size--;
            return true;
        }

        public int getFront() { return isEmpty() ? -1 : data[front]; }
        public int getRear() { return isEmpty() ? -1 : data[rear]; }
        public boolean isEmpty() { return size == 0; }
        public boolean isFull() { return size == cap; }
    }

    public static void main(String[] args) {
        MyCircularDeque dq = new MyCircularDeque(3);
        assert dq.insertLast(1);
        assert dq.insertLast(2);
        assert dq.insertFront(3);
        assert !dq.insertFront(4);
        assert dq.getRear() == 2;
        assert dq.isFull();
        assert dq.deleteLast();
        assert dq.insertFront(4);
        assert dq.getFront() == 4;

        System.out.println("All tests passed!");
    }
}
