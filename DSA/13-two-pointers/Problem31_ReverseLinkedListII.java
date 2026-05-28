/**
 * Problem 31: Reverse Linked List II
 * 
 * Reverse nodes from position left to right (1-indexed).
 * 
 * Approach: Navigate to position left-1, reverse the sublist, reconnect.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like reversing a segment of a processing pipeline
 * for rollback while keeping the rest of the pipeline intact.
 */
public class Problem31_ReverseLinkedListII {
    static class ListNode {
        int val; ListNode next;
        ListNode(int v) { val = v; }
    }

    public static ListNode reverseBetween(ListNode head, int left, int right) {
        ListNode dummy = new ListNode(0);
        dummy.next = head;
        ListNode prev = dummy;
        for (int i = 1; i < left; i++) prev = prev.next;
        ListNode curr = prev.next;
        for (int i = 0; i < right - left; i++) {
            ListNode next = curr.next;
            curr.next = next.next;
            next.next = prev.next;
            prev.next = next;
        }
        return dummy.next;
    }

    public static void main(String[] args) {
        ListNode h = new ListNode(1); h.next = new ListNode(2); h.next.next = new ListNode(3);
        h.next.next.next = new ListNode(4); h.next.next.next.next = new ListNode(5);
        ListNode r = reverseBetween(h, 2, 4);
        while (r != null) { System.out.print(r.val + " "); r = r.next; } // 1 4 3 2 5
        System.out.println();
    }
}
