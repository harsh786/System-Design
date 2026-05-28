/**
 * Problem 18: Remove Duplicates from Sorted List II - Remove ALL duplicated nodes
 * 
 * Approach: Use dummy node. If curr.next has duplicates, skip all of them.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Quarantining all poisoned messages in a queue, not just extras.
 */
public class Problem18_RemoveDuplicatesFromSortedListII {
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode deleteDuplicates(ListNode head) {
        ListNode dummy = new ListNode(0, head), prev = dummy;
        while (prev.next != null) {
            ListNode curr = prev.next;
            if (curr.next != null && curr.val == curr.next.val) {
                while (curr.next != null && curr.val == curr.next.val) curr = curr.next;
                prev.next = curr.next;
            } else {
                prev = prev.next;
            }
        }
        return dummy.next;
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(1, new ListNode(2, new ListNode(3, new ListNode(3, new ListNode(4, new ListNode(4, new ListNode(5)))))));
        System.out.println("Test1: " + toString(deleteDuplicates(h1))); // 1->2->5->null

        ListNode h2 = new ListNode(1, new ListNode(1, new ListNode(1, new ListNode(2, new ListNode(3)))));
        System.out.println("Test2: " + toString(deleteDuplicates(h2))); // 2->3->null
    }
}
