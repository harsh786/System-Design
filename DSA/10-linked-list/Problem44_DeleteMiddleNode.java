/**
 * Problem 44: Delete the Middle Node of a Linked List
 * 
 * Approach: Slow/fast pointers. Use prev pointer to delete middle.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Removing the median-latency server from a pool
 * to test if it's causing P50 degradation.
 */
public class Problem44_DeleteMiddleNode {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode deleteMiddle(ListNode head) {
        if (head == null || head.next == null) return null;
        ListNode slow = head, fast = head, prev = null;
        while (fast != null && fast.next != null) { prev = slow; slow = slow.next; fast = fast.next.next; }
        prev.next = slow.next;
        return head;
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(1, new ListNode(3, new ListNode(4, new ListNode(7, new ListNode(1, new ListNode(2, new ListNode(6)))))));
        System.out.println("Test1: " + toString(deleteMiddle(h1))); // 1->3->4->1->2->6->null

        ListNode h2 = new ListNode(1, new ListNode(2, new ListNode(3, new ListNode(4))));
        System.out.println("Test2: " + toString(deleteMiddle(h2))); // 1->2->4->null

        System.out.println("Test3: " + toString(deleteMiddle(new ListNode(1)))); // null
    }
}
