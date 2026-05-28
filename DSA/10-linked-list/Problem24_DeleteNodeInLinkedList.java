/**
 * Problem 24: Delete Node in a Linked List (given only access to that node)
 * 
 * Approach: Copy next node's value to current, then skip next node.
 * Time Complexity: O(1)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Like replacing a failed pod in-place by copying the next
 * pod's state and removing the next pod from the chain.
 */
public class Problem24_DeleteNodeInLinkedList {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static void deleteNode(ListNode node) {
        node.val = node.next.val;
        node.next = node.next.next;
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(4, new ListNode(5, new ListNode(1, new ListNode(9))));
        deleteNode(h1.next); // delete node with val 5
        System.out.println("Test1: " + toString(h1)); // 4->1->9->null

        ListNode h2 = new ListNode(4, new ListNode(5, new ListNode(1, new ListNode(9))));
        deleteNode(h2.next.next); // delete node with val 1
        System.out.println("Test2: " + toString(h2)); // 4->5->9->null
    }
}
