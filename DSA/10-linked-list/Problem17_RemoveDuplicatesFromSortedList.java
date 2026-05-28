/**
 * Problem 17: Remove Duplicates from Sorted List
 * 
 * Approach: Skip consecutive duplicates by adjusting next pointers.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Deduplication in a sorted event log before archival.
 */
public class Problem17_RemoveDuplicatesFromSortedList {
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode deleteDuplicates(ListNode head) {
        ListNode curr = head;
        while (curr != null && curr.next != null) {
            if (curr.val == curr.next.val) curr.next = curr.next.next;
            else curr = curr.next;
        }
        return head;
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(1, new ListNode(1, new ListNode(2)));
        System.out.println("Test1: " + toString(deleteDuplicates(h1))); // 1->2->null

        ListNode h2 = new ListNode(1, new ListNode(1, new ListNode(2, new ListNode(3, new ListNode(3)))));
        System.out.println("Test2: " + toString(deleteDuplicates(h2))); // 1->2->3->null
    }
}
