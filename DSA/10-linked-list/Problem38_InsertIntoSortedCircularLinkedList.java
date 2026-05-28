/**
 * Problem 38: Insert into a Sorted Circular Linked List
 * 
 * Approach: Find insertion point: between two nodes where prev<=val<=next,
 * or at the max/min boundary, or single-node list.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Inserting a new server into a consistent hash ring
 * at the correct position based on its hash value.
 */
public class Problem38_InsertIntoSortedCircularLinkedList {
    static class Node {
        int val; Node next;
        Node(int v) { val = v; }
        Node(int v, Node n) { val = v; next = n; }
    }

    public static Node insert(Node head, int insertVal) {
        Node node = new Node(insertVal);
        if (head == null) { node.next = node; return node; }
        Node prev = head, curr = head.next;
        boolean inserted = false;
        do {
            if (prev.val <= insertVal && insertVal <= curr.val) { // normal case
                prev.next = node; node.next = curr; inserted = true; break;
            }
            if (prev.val > curr.val) { // at boundary (max->min)
                if (insertVal >= prev.val || insertVal <= curr.val) {
                    prev.next = node; node.next = curr; inserted = true; break;
                }
            }
            prev = curr; curr = curr.next;
        } while (prev != head);
        if (!inserted) { prev.next = node; node.next = curr; } // all same values
        return head;
    }

    static void printCircular(Node head, int count) {
        Node curr = head;
        for (int i = 0; i < count; i++) { System.out.print(curr.val + "->"); curr = curr.next; }
        System.out.println("(cycle)");
    }

    public static void main(String[] args) {
        Node n1 = new Node(3), n2 = new Node(4), n3 = new Node(1);
        n1.next = n2; n2.next = n3; n3.next = n1;
        insert(n1, 2);
        printCircular(n1, 4); // 3->4->1->2->(cycle)

        // Insert into null
        Node result = insert(null, 1);
        System.out.println("Single: " + result.val + " next=" + (result.next == result)); // true
    }
}
