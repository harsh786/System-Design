/**
 * Problem 34: Design Circular Deque
 * 
 * Approach: Doubly linked list with size tracking and capacity limit.
 * Time Complexity: O(1) for all operations
 * Space Complexity: O(k)
 * 
 * Production Analogy: Bounded work-stealing deque in thread pools - workers push/pop
 * from both ends with fixed capacity.
 */
public class Problem34_DesignCircularDeque {
    static class Node {
        int val; Node prev, next;
        Node(int v) { val = v; }
    }

    static class MyCircularDeque {
        Node head, tail;
        int size, capacity;

        public MyCircularDeque(int k) { capacity = k; head = new Node(0); tail = new Node(0); head.next=tail; tail.prev=head; }

        public boolean insertFront(int value) {
            if (isFull()) return false;
            Node node = new Node(value);
            node.next = head.next; node.prev = head;
            head.next.prev = node; head.next = node;
            size++; return true;
        }

        public boolean insertLast(int value) {
            if (isFull()) return false;
            Node node = new Node(value);
            node.prev = tail.prev; node.next = tail;
            tail.prev.next = node; tail.prev = node;
            size++; return true;
        }

        public boolean deleteFront() {
            if (isEmpty()) return false;
            head.next = head.next.next; head.next.prev = head;
            size--; return true;
        }

        public boolean deleteLast() {
            if (isEmpty()) return false;
            tail.prev = tail.prev.prev; tail.prev.next = tail;
            size--; return true;
        }

        public int getFront() { return isEmpty() ? -1 : head.next.val; }
        public int getRear() { return isEmpty() ? -1 : tail.prev.val; }
        public boolean isEmpty() { return size == 0; }
        public boolean isFull() { return size == capacity; }
    }

    public static void main(String[] args) {
        MyCircularDeque dq = new MyCircularDeque(3);
        System.out.println(dq.insertLast(1));  // true
        System.out.println(dq.insertLast(2));  // true
        System.out.println(dq.insertFront(3)); // true
        System.out.println(dq.insertFront(4)); // false (full)
        System.out.println(dq.getRear());      // 2
        System.out.println(dq.isFull());       // true
        System.out.println(dq.deleteLast());   // true
        System.out.println(dq.insertFront(4)); // true
        System.out.println(dq.getFront());     // 4
    }
}
