/**
 * Problem 33: Merge Two Sorted Lists
 * 
 * Merge two sorted linked lists into one sorted list.
 * 
 * Approach: Two pointers, compare and link smaller node.
 * Time: O(m+n), Space: O(1)
 * 
 * Production Analogy: Like merging two sorted event streams from different
 * data centers into a single globally ordered stream.
 */
public class Problem33_MergeTwoSortedLists {
    static class ListNode {
        int val; ListNode next;
        ListNode(int v) { val = v; }
    }

    public static ListNode mergeTwoLists(ListNode l1, ListNode l2) {
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
        ListNode l1 = new ListNode(1); l1.next = new ListNode(2); l1.next.next = new ListNode(4);
        ListNode l2 = new ListNode(1); l2.next = new ListNode(3); l2.next.next = new ListNode(4);
        ListNode r = mergeTwoLists(l1, l2);
        while (r != null) { System.out.print(r.val + " "); r = r.next; } // 1 1 2 3 4 4
        System.out.println();
    }
}
