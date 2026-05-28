/**
 * Problem 8: Copy List with Random Pointer
 * 
 * Approach: Interleave cloned nodes, set random pointers, then separate lists.
 * Time Complexity: O(n)
 * Space Complexity: O(1) extra (excluding output)
 * 
 * Production Analogy: Deep cloning a distributed state machine where nodes have
 * both sequential and cross-partition references (like DB foreign keys).
 */
import java.util.*;

public class Problem08_CopyListWithRandomPointer {
    static class Node {
        int val;
        Node next, random;
        Node(int val) { this.val = val; }
    }

    public static Node copyRandomList(Node head) {
        if (head == null) return null;
        // Step 1: Interleave
        Node curr = head;
        while (curr != null) {
            Node copy = new Node(curr.val);
            copy.next = curr.next;
            curr.next = copy;
            curr = copy.next;
        }
        // Step 2: Set random
        curr = head;
        while (curr != null) {
            if (curr.random != null) curr.next.random = curr.random.next;
            curr = curr.next.next;
        }
        // Step 3: Separate
        Node dummy = new Node(0), tail = dummy;
        curr = head;
        while (curr != null) {
            tail.next = curr.next;
            tail = tail.next;
            curr.next = curr.next.next;
            curr = curr.next;
        }
        return dummy.next;
    }

    public static void main(String[] args) {
        Node n1 = new Node(7), n2 = new Node(13), n3 = new Node(11);
        n1.next = n2; n2.next = n3;
        n1.random = null; n2.random = n1; n3.random = n2;
        Node copy = copyRandomList(n1);
        System.out.println("Test1: " + copy.val + " -> " + copy.next.val + " -> " + copy.next.next.val);
        System.out.println("Random check: " + (copy.next.random == copy)); // true

        System.out.println("Test2 (null): " + copyRandomList(null)); // null
    }
}
