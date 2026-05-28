/**
 * Problem 5: Remove Nth Node From End of List
 * 
 * Approach: Two pointers with n gap. When fast reaches end, slow is at target.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Like removing the nth most recent log entry from a rolling
 * window buffer without knowing total size upfront.
 */
public class Problem05_RemoveNthNodeFromEnd {
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode removeNthFromEnd(ListNode head, int n) {
        ListNode dummy = new ListNode(0, head);
        ListNode fast = dummy, slow = dummy;
        for (int i = 0; i <= n; i++) fast = fast.next;
        while (fast != null) { fast = fast.next; slow = slow.next; }
        slow.next = slow.next.next;
        return dummy.next;
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(1, new ListNode(2, new ListNode(3, new ListNode(4, new ListNode(5)))));
        System.out.println("Test1: " + toString(removeNthFromEnd(h1, 2))); // 1->2->3->5->null

        ListNode h2 = new ListNode(1);
        System.out.println("Test2: " + toString(removeNthFromEnd(h2, 1))); // null

        ListNode h3 = new ListNode(1, new ListNode(2));
        System.out.println("Test3: " + toString(removeNthFromEnd(h3, 1))); // 1->null
    }
}
