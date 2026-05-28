/**
 * Problem 14: Rotate List - Rotate list to the right by k places
 * 
 * Approach: Find length, make circular, break at (len - k % len) position.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Like rotating log file partitions - the tail becomes the
 * new head when partitions are cycled for archival.
 */
public class Problem14_RotateList {
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode rotateRight(ListNode head, int k) {
        if (head == null || head.next == null || k == 0) return head;
        int len = 1;
        ListNode tail = head;
        while (tail.next != null) { tail = tail.next; len++; }
        k = k % len;
        if (k == 0) return head;
        tail.next = head; // make circular
        int stepsToNewTail = len - k;
        ListNode newTail = head;
        for (int i = 1; i < stepsToNewTail; i++) newTail = newTail.next;
        ListNode newHead = newTail.next;
        newTail.next = null;
        return newHead;
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(1, new ListNode(2, new ListNode(3, new ListNode(4, new ListNode(5)))));
        System.out.println("Test1: " + toString(rotateRight(h1, 2))); // 4->5->1->2->3->null

        ListNode h2 = new ListNode(0, new ListNode(1, new ListNode(2)));
        System.out.println("Test2: " + toString(rotateRight(h2, 4))); // 2->0->1->null
    }
}
