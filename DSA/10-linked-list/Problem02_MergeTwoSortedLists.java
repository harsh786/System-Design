/**
 * Problem 2: Merge Two Sorted Lists (LeetCode 21)
 * 
 * Approach: Use dummy head, compare nodes from both lists, append smaller one.
 * Time: O(n+m), Space: O(1)
 * 
 * Production Analogy: Merging two sorted event streams (e.g., Kafka partitions)
 * into a single ordered stream for downstream consumers.
 */
public class Problem02_MergeTwoSortedLists {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
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

    static ListNode buildList(int... vals) {
        ListNode dummy = new ListNode(0), curr = dummy;
        for (int v : vals) { curr.next = new ListNode(v); curr = curr.next; }
        return dummy.next;
    }

    static String listToString(ListNode head) {
        StringBuilder sb = new StringBuilder();
        while (head != null) { sb.append(head.val).append("->"); head = head.next; }
        return sb.append("null").toString();
    }

    public static void main(String[] args) {
        System.out.println(listToString(mergeTwoLists(buildList(1,2,4), buildList(1,3,4))));
        System.out.println(listToString(mergeTwoLists(null, null)));
        System.out.println(listToString(mergeTwoLists(null, buildList(0))));
        System.out.println(listToString(mergeTwoLists(buildList(1), buildList(2))));
    }
}
