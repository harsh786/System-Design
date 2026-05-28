/**
 * Problem 13: Insertion Sort List
 * 
 * Approach: Build sorted list by inserting each node at correct position.
 * Time Complexity: O(n^2)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Like inserting events into a sorted timeline - each new event
 * scans for its chronological position.
 */
public class Problem13_InsertionSortList {
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode insertionSortList(ListNode head) {
        ListNode dummy = new ListNode(Integer.MIN_VALUE);
        ListNode curr = head;
        while (curr != null) {
            ListNode next = curr.next;
            ListNode prev = dummy;
            while (prev.next != null && prev.next.val < curr.val) prev = prev.next;
            curr.next = prev.next;
            prev.next = curr;
            curr = next;
        }
        return dummy.next;
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(4, new ListNode(2, new ListNode(1, new ListNode(3))));
        System.out.println("Test1: " + toString(insertionSortList(h1)));

        ListNode h2 = new ListNode(-1, new ListNode(5, new ListNode(3, new ListNode(4, new ListNode(0)))));
        System.out.println("Test2: " + toString(insertionSortList(h2)));
    }
}
