/**
 * Problem 29: Reorder List
 * 
 * Reorder L0→L1→...→Ln to L0→Ln→L1→Ln-1→...
 * 
 * Approach: Find middle, reverse second half, merge alternately.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like interleaving hot and cold cache entries for
 * balanced memory access patterns across cache lines.
 */
public class Problem29_ReorderList {
    static class ListNode {
        int val; ListNode next;
        ListNode(int v) { val = v; }
    }

    public static void reorderList(ListNode head) {
        if (head == null || head.next == null) return;
        // Find middle
        ListNode slow = head, fast = head;
        while (fast.next != null && fast.next.next != null) { slow = slow.next; fast = fast.next.next; }
        // Reverse second half
        ListNode prev = null, curr = slow.next;
        slow.next = null;
        while (curr != null) { ListNode next = curr.next; curr.next = prev; prev = curr; curr = next; }
        // Merge
        ListNode first = head, second = prev;
        while (second != null) {
            ListNode tmp1 = first.next, tmp2 = second.next;
            first.next = second; second.next = tmp1;
            first = tmp1; second = tmp2;
        }
    }

    public static void main(String[] args) {
        ListNode h = new ListNode(1); h.next = new ListNode(2); h.next.next = new ListNode(3); h.next.next.next = new ListNode(4);
        reorderList(h);
        ListNode c = h;
        while (c != null) { System.out.print(c.val + " "); c = c.next; } // 1 4 2 3
        System.out.println();
    }
}
