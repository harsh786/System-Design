/**
 * Problem 50: Deque with Doubly Linked List
 * 
 * Approach: Full deque implementation with DLL. O(1) operations at both ends.
 * Time Complexity: O(1) for all push/pop/peek operations
 * Space Complexity: O(n)
 * 
 * Production Analogy: Work-stealing thread pool deque - owner pushes/pops from one end,
 * thieves steal from the other end for load balancing.
 */
public class Problem50_DequeWithDoublyLinkedList {
    static class Node {
        int val;
        Node prev, next;
        Node(int v) { val = v; }
    }

    static class Deque {
        private Node head, tail;
        private int size;

        public Deque() { head = new Node(0); tail = new Node(0); head.next = tail; tail.prev = head; }

        public void pushFront(int val) {
            Node node = new Node(val);
            node.next = head.next; node.prev = head;
            head.next.prev = node; head.next = node;
            size++;
        }

        public void pushBack(int val) {
            Node node = new Node(val);
            node.prev = tail.prev; node.next = tail;
            tail.prev.next = node; tail.prev = node;
            size++;
        }

        public int popFront() {
            if (isEmpty()) throw new RuntimeException("Empty");
            Node node = head.next;
            head.next = node.next; node.next.prev = head;
            size--;
            return node.val;
        }

        public int popBack() {
            if (isEmpty()) throw new RuntimeException("Empty");
            Node node = tail.prev;
            tail.prev = node.prev; node.prev.next = tail;
            size--;
            return node.val;
        }

        public int peekFront() { return isEmpty() ? -1 : head.next.val; }
        public int peekBack() { return isEmpty() ? -1 : tail.prev.val; }
        public boolean isEmpty() { return size == 0; }
        public int size() { return size; }
    }

    public static void main(String[] args) {
        Deque dq = new Deque();
        dq.pushFront(1); dq.pushFront(2); dq.pushBack(3); dq.pushBack(4);
        // State: 2->1->3->4
        System.out.println("Front: " + dq.peekFront()); // 2
        System.out.println("Back: " + dq.peekBack());   // 4
        System.out.println("PopFront: " + dq.popFront()); // 2
        System.out.println("PopBack: " + dq.popBack());   // 4
        System.out.println("Size: " + dq.size());         // 2
        System.out.println("Front: " + dq.peekFront()); // 1
        System.out.println("Back: " + dq.peekBack());   // 3
        System.out.println("Empty: " + dq.isEmpty());   // false
        dq.popFront(); dq.popFront();
        System.out.println("Empty: " + dq.isEmpty());   // true
    }
}
