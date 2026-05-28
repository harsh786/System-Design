/**
 * Problem 12: Sort List (Merge Sort)
 * 
 * Approach: Top-down merge sort - find middle, split, sort halves, merge.
 * Time Complexity: O(n log n)
 * Space Complexity: O(log n) recursion stack
 * 
 * Production Analogy: Like external sort for large datasets that don't fit in memory -
 * split into chunks, sort each, then merge sorted runs.
 */
public class Problem12_SortList {
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode sortList(ListNode head) {
        if (head == null || head.next == null) return head;
        ListNode slow = head, fast = head.next;
        while (fast != null && fast.next != null) { slow = slow.next; fast = fast.next.next; }
        ListNode mid = slow.next;
        slow.next = null;
        ListNode left = sortList(head), right = sortList(mid);
        return merge(left, right);
    }

    private static ListNode merge(ListNode l1, ListNode l2) {
        ListNode dummy = new ListNode(0), tail = dummy;
        while (l1 != null && l2 != null) {
            if (l1.val <= l2.val) { tail.next = l1; l1 = l1.next; }
            else { tail.next = l2; l2 = l2.next; }
            tail = tail.next;
        }
        tail.next = (l1 != null) ? l1 : l2;
        return dummy.next;
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(4, new ListNode(2, new ListNode(1, new ListNode(3))));
        System.out.println("Test1: " + toString(sortList(h1))); // 1->2->3->4->null

        ListNode h2 = new ListNode(-1, new ListNode(5, new ListNode(3, new ListNode(4, new ListNode(0)))));
        System.out.println("Test2: " + toString(sortList(h2)));

        System.out.println("Test3: " + toString(sortList(null))); // null
    }
}
