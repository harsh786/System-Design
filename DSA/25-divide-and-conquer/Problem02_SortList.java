/**
 * Problem 2: Sort List (LeetCode 148)
 * Sort a linked list in O(n log n) time using constant space.
 * 
 * D&C Approach:
 * - DIVIDE: Use slow/fast pointers to find middle, split list into two halves
 * - CONQUER: Recursively sort each half
 * - COMBINE: Merge two sorted linked lists
 * 
 * Recurrence: T(n) = 2T(n/2) + O(n)
 * Time: O(n log n), Space: O(log n) for recursion stack
 * 
 * Production Analogy:
 * - Sorting streaming data where random access is expensive (linked structure)
 * - Log file sorting in distributed systems where data arrives as linked chunks
 */
public class Problem02_SortList {

    static class ListNode {
        int val;
        ListNode next;
        ListNode(int val) { this.val = val; }
    }

    public static ListNode sortList(ListNode head) {
        if (head == null || head.next == null) return head;
        
        // Find middle using slow/fast pointer
        ListNode slow = head, fast = head.next;
        while (fast != null && fast.next != null) {
            slow = slow.next;
            fast = fast.next.next;
        }
        
        ListNode mid = slow.next;
        slow.next = null; // Split the list
        
        ListNode left = sortList(head);
        ListNode right = sortList(mid);
        
        return merge(left, right);
    }

    private static ListNode merge(ListNode l1, ListNode l2) {
        ListNode dummy = new ListNode(0);
        ListNode curr = dummy;
        while (l1 != null && l2 != null) {
            if (l1.val <= l2.val) { curr.next = l1; l1 = l1.next; }
            else { curr.next = l2; l2 = l2.next; }
            curr = curr.next;
        }
        curr.next = (l1 != null) ? l1 : l2;
        return dummy.next;
    }

    private static ListNode buildList(int[] vals) {
        ListNode dummy = new ListNode(0);
        ListNode curr = dummy;
        for (int v : vals) { curr.next = new ListNode(v); curr = curr.next; }
        return dummy.next;
    }

    private static String listToString(ListNode head) {
        StringBuilder sb = new StringBuilder("[");
        while (head != null) {
            sb.append(head.val);
            if (head.next != null) sb.append(", ");
            head = head.next;
        }
        return sb.append("]").toString();
    }

    public static void main(String[] args) {
        System.out.println(listToString(sortList(buildList(new int[]{4, 2, 1, 3}))));
        System.out.println(listToString(sortList(buildList(new int[]{-1, 5, 3, 4, 0}))));
        System.out.println(listToString(sortList(buildList(new int[]{}))));
        System.out.println(listToString(sortList(buildList(new int[]{1}))));
        System.out.println(listToString(sortList(buildList(new int[]{2, 1}))));
    }
}
