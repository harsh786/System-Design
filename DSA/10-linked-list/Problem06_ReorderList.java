/**
 * Problem 6: Reorder List
 * L0→L1→...→Ln-1→Ln becomes L0→Ln→L1→Ln-1→L2→Ln-2→...
 * 
 * Approach: 1) Find middle 2) Reverse second half 3) Merge alternately
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Like interleaving priority requests with normal requests
 * in a load balancer to ensure fair processing distribution.
 */
public class Problem06_ReorderList {
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
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
            ListNode t1 = first.next, t2 = second.next;
            first.next = second; second.next = t1;
            first = t1; second = t2;
        }
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(1, new ListNode(2, new ListNode(3, new ListNode(4))));
        reorderList(h1);
        System.out.println("Test1: " + toString(h1)); // 1->4->2->3->null

        ListNode h2 = new ListNode(1, new ListNode(2, new ListNode(3, new ListNode(4, new ListNode(5)))));
        reorderList(h2);
        System.out.println("Test2: " + toString(h2)); // 1->5->2->4->3->null
    }
}
