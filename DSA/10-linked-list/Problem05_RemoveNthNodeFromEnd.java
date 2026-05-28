/**
 * Problem 5: Remove Nth Node From End of List (LeetCode 19)
 * 
 * Approach: Two pointers - advance fast n steps ahead, then move both until fast reaches end.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like removing the nth most recent entry from a rolling log buffer
 * without knowing total size upfront (streaming data).
 */
public class Problem05_RemoveNthNodeFromEnd {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
    }

    public static ListNode removeNthFromEnd(ListNode head, int n) {
        ListNode dummy = new ListNode(0);
        dummy.next = head;
        ListNode fast = dummy, slow = dummy;
        for (int i = 0; i <= n; i++) fast = fast.next;
        while (fast != null) { fast = fast.next; slow = slow.next; }
        slow.next = slow.next.next;
        return dummy.next;
    }

    static ListNode buildList(int... vals) {
        ListNode dummy = new ListNode(0), curr = dummy;
        for (int v : vals) { curr.next = new ListNode(v); curr = curr.next; }
        return dummy.next;
    }

    static String listToString(ListNode head) {
        StringBuilder sb = new StringBuilder();
        while (head != null) { sb.append(head.val).append("->"); head = head.next; }
        return sb.append("null").toString();
    }

    public static void main(String[] args) {
        System.out.println(listToString(removeNthFromEnd(buildList(1,2,3,4,5), 2))); // 1->2->3->5->null
        System.out.println(listToString(removeNthFromEnd(buildList(1), 1))); // null
        System.out.println(listToString(removeNthFromEnd(buildList(1,2), 1))); // 1->null
        System.out.println(listToString(removeNthFromEnd(buildList(1,2), 2))); // 2->null
    }
}
