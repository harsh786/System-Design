/**
 * Problem 12: Sort List (LeetCode 148)
 * 
 * Approach: Merge Sort - find middle, recursively sort halves, merge.
 * Time: O(n log n), Space: O(log n) stack
 * 
 * Production Analogy: External merge sort for sorting data that doesn't fit in memory -
 * used in database query engines for ORDER BY on large datasets.
 */
public class Problem12_SortList {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
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
        System.out.println(listToString(sortList(buildList(4,2,1,3)))); // 1->2->3->4->null
        System.out.println(listToString(sortList(buildList(-1,5,3,4,0)))); // -1->0->3->4->5->null
        System.out.println(listToString(sortList(null))); // null
    }
}
