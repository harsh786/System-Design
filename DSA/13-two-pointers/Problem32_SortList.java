/**
 * Problem 32: Sort List
 * 
 * Sort a linked list in O(n log n) time and O(1) space.
 * 
 * Approach: Merge sort - find middle (slow/fast), split, recursively sort, merge.
 * Time: O(n log n), Space: O(log n) for recursion stack
 * 
 * Production Analogy: Like external sort for large datasets that don't fit
 * in memory - split into chunks, sort each, merge results.
 */
public class Problem32_SortList {
    static class ListNode {
        int val; ListNode next;
        ListNode(int v) { val = v; }
    }

    public static ListNode sortList(ListNode head) {
        if (head == null || head.next == null) return head;
        ListNode slow = head, fast = head.next;
        while (fast != null && fast.next != null) { slow = slow.next; fast = fast.next.next; }
        ListNode mid = slow.next;
        slow.next = null;
        ListNode left = sortList(head);
        ListNode right = sortList(mid);
        return merge(left, right);
    }

    private static ListNode merge(ListNode l1, ListNode l2) {
        ListNode dummy = new ListNode(0), curr = dummy;
        while (l1 != null && l2 != null) {
            if (l1.val <= l2.val) { curr.next = l1; l1 = l1.next; }
            else { curr.next = l2; l2 = l2.next; }
            curr = curr.next;
        }
        curr.next = (l1 != null) ? l1 : l2;
        return dummy.next;
    }

    public static void main(String[] args) {
        ListNode h = new ListNode(4); h.next = new ListNode(2); h.next.next = new ListNode(1); h.next.next.next = new ListNode(3);
        ListNode r = sortList(h);
        while (r != null) { System.out.print(r.val + " "); r = r.next; } // 1 2 3 4
        System.out.println();
    }
}
