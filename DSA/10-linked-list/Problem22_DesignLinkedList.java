/**
 * Problem 22: Design Linked List
 * 
 * Approach: Doubly linked list with sentinel head/tail for clean edge cases.
 * Time Complexity: O(n) for get/addAtIndex/deleteAtIndex, O(1) for head/tail ops
 * Space Complexity: O(n)
 * 
 * Production Analogy: Building the underlying data structure for an ordered
 * message queue with O(1) enqueue/dequeue at both ends.
 */
public class Problem22_DesignLinkedList {
    static class MyLinkedList {
        private int size;
        private int[] vals;
        private int[] next, prev;
        // Simpler: just use node-based approach
        private Node head, tail;

        static class Node { int val; Node prev, next; Node(int v){val=v;} }

        public MyLinkedList() { head = new Node(0); tail = new Node(0); head.next=tail; tail.prev=head; size=0; }

        public int get(int index) {
            if (index<0||index>=size) return -1;
            Node curr = head.next;
            for (int i=0;i<index;i++) curr=curr.next;
            return curr.val;
        }

        public void addAtHead(int val) { addAtIndex(0, val); }
        public void addAtTail(int val) { addAtIndex(size, val); }

        public void addAtIndex(int index, int val) {
            if (index<0||index>size) return;
            Node pred = head;
            for (int i=0;i<index;i++) pred=pred.next;
            Node succ = pred.next;
            Node node = new Node(val);
            node.prev=pred; node.next=succ;
            pred.next=node; succ.prev=node;
            size++;
        }

        public void deleteAtIndex(int index) {
            if (index<0||index>=size) return;
            Node pred = head;
            for (int i=0;i<index;i++) pred=pred.next;
            Node del = pred.next;
            pred.next=del.next; del.next.prev=pred;
            size--;
        }
    }

    public static void main(String[] args) {
        MyLinkedList ll = new MyLinkedList();
        ll.addAtHead(1); ll.addAtTail(3); ll.addAtIndex(1,2);
        System.out.println(ll.get(1)); // 2
        ll.deleteAtIndex(1);
        System.out.println(ll.get(1)); // 3
        System.out.println(ll.get(5)); // -1
    }
}
