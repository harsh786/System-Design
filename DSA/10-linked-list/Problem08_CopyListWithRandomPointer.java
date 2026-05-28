/**
 * Problem 8: Copy List with Random Pointer (LeetCode 138)
 * 
 * Approach: Interleave cloned nodes, set random pointers, then separate lists.
 * Time: O(n), Space: O(1) extra (excluding output)
 * 
 * Production Analogy: Deep cloning a complex object graph with circular references -
 * like serializing/deserializing microservice state with cross-references.
 */
import java.util.*;

public class Problem08_CopyListWithRandomPointer {
    static class Node {
        int val; Node next, random;
        Node(int val) { this.val = val; }
    }

    // HashMap approach (clearer)
    public static Node copyRandomList(Node head) {
        if (head == null) return null;
        Map<Node, Node> map = new HashMap<>();
        Node curr = head;
        while (curr != null) { map.put(curr, new Node(curr.val)); curr = curr.next; }
        curr = head;
        while (curr != null) {
            map.get(curr).next = map.get(curr.next);
            map.get(curr).random = map.get(curr.random);
            curr = curr.next;
        }
        return map.get(head);
    }

    // O(1) space approach: interleave
    public static Node copyRandomListO1(Node head) {
        if (head == null) return null;
        // Step 1: Interleave
        Node curr = head;
        while (curr != null) {
            Node clone = new Node(curr.val);
            clone.next = curr.next; curr.next = clone; curr = clone.next;
        }
        // Step 2: Set random
        curr = head;
        while (curr != null) {
            if (curr.random != null) curr.next.random = curr.random.next;
            curr = curr.next.next;
        }
        // Step 3: Separate
        Node dummy = new Node(0), cloneCurr = dummy;
        curr = head;
        while (curr != null) {
            cloneCurr.next = curr.next; cloneCurr = cloneCurr.next;
            curr.next = curr.next.next; curr = curr.next;
        }
        return dummy.next;
    }

    public static void main(String[] args) {
        // Test: [[7,null],[13,0],[11,4],[10,2],[1,0]]
        Node n1 = new Node(7), n2 = new Node(13), n3 = new Node(11), n4 = new Node(10), n5 = new Node(1);
        n1.next = n2; n2.next = n3; n3.next = n4; n4.next = n5;
        n1.random = null; n2.random = n1; n3.random = n5; n4.random = n3; n5.random = n1;

        Node copy = copyRandomList(n1);
        Node c = copy;
        while (c != null) {
            System.out.print("[" + c.val + "," + (c.random != null ? c.random.val : "null") + "] ");
            c = c.next;
        }
        System.out.println();

        // Verify deep copy (different references)
        System.out.println(copy != n1); // true

        // Test null
        System.out.println(copyRandomList(null)); // null
    }
}
