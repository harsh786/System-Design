import java.util.*;

/**
 * Problem 13: Copy List with Random Pointer
 * Deep copy a linked list where each node has a next and a random pointer.
 *
 * Approach: Use HashMap mapping original node -> cloned node.
 * First pass: create all cloned nodes. Second pass: assign next and random pointers.
 *
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 *
 * Production Analogy: Like deep cloning a microservice dependency graph for staging environment.
 * Each service (node) may reference arbitrary other services (random pointer).
 */
public class Problem13_CopyListWithRandomPointer {
    static class Node {
        int val;
        Node next, random;
        Node(int val) { this.val = val; }
    }

    public Node copyRandomList(Node head) {
        if (head == null) return null;
        Map<Node, Node> map = new HashMap<>();
        Node curr = head;
        while (curr != null) {
            map.put(curr, new Node(curr.val));
            curr = curr.next;
        }
        curr = head;
        while (curr != null) {
            map.get(curr).next = map.get(curr.next);
            map.get(curr).random = map.get(curr.random);
            curr = curr.next;
        }
        return map.get(head);
    }

    public static void main(String[] args) {
        // Test: 1->2->3, 1.random=3, 2.random=1, 3.random=2
        Node n1 = new Node(1), n2 = new Node(2), n3 = new Node(3);
        n1.next = n2; n2.next = n3;
        n1.random = n3; n2.random = n1; n3.random = n2;

        Problem13_CopyListWithRandomPointer sol = new Problem13_CopyListWithRandomPointer();
        Node copy = sol.copyRandomList(n1);
        System.out.println(copy.val + " random:" + copy.random.val); // 1 random:3
        System.out.println(copy.next.val + " random:" + copy.next.random.val); // 2 random:1
        System.out.println(sol.copyRandomList(null) == null); // true
    }
}
