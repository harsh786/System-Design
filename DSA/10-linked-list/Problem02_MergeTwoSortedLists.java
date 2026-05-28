/**
 * Problem 2: Merge Two Sorted Lists
 * 
 * Approach: Use dummy head, compare nodes from both lists, append smaller one.
 * Time Complexity: O(n + m)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Like merging two sorted event streams (e.g., Kafka topics) 
 * into a single ordered stream for downstream consumers.
 */
public class Problem02_MergeTwoSortedLists {
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode mergeTwoLists(ListNode l1, ListNode l2) {
        ListNode dummy = new ListNode(0), tail = dummy;
        while (l1 != null && l2 != null) {
            if (l1.val <= l2.val) { tail.next = l1; l1 = l1.next; }
            else { tail.next = l2; l2 = l2.next; }
            tail = tail.next;
        }
        tail.next = (l1 != null) ? l1 : l2;
        return dummy.next;
    }

    static String toString(ListNode head) {
        StringBuilder sb = new StringBuilder();
        while (head != null) { sb.append(head.val).append("->"); head = head.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        ListNode l1 = new ListNode(1, new ListNode(2, new ListNode(4)));
        ListNode l2 = new ListNode(1, new ListNode(3, new ListNode(4)));
        System.out.println("Test1: " + toString(mergeTwoLists(l1, l2)));

        System.out.println("Test2: " + toString(mergeTwoLists(null, null)));
        System.out.println("Test3: " + toString(mergeTwoLists(null, new ListNode(0))));
    }
}
