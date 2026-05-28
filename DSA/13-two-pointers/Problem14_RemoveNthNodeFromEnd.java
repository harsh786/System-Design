/**
 * Problem 14: Remove Nth Node From End of List
 * 
 * Remove the nth node from the end of a linked list.
 * 
 * Approach: Two pointers with n gap. When fast reaches end, slow is at target.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like removing the nth most recent entry from a
 * circular buffer by maintaining a fixed-distance offset pointer.
 */
public class Problem14_RemoveNthNodeFromEnd {
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int v) { val = v; }
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

    public static void main(String[] args) {
        ListNode head = new ListNode(1);
        head.next = new ListNode(2);
        head.next.next = new ListNode(3);
        head.next.next.next = new ListNode(4);
        head.next.next.next.next = new ListNode(5);
        ListNode result = removeNthFromEnd(head, 2);
        while (result != null) { System.out.print(result.val + " "); result = result.next; }
        // 1 2 3 5
        System.out.println();

        ListNode single = new ListNode(1);
        ListNode r2 = removeNthFromEnd(single, 1);
        System.out.println(r2); // null
    }
}
