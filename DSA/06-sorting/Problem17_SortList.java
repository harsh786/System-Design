import java.util.*;

/**
 * Problem 17: Sort List
 * 
 * Sort a linked list in O(n log n) time and O(1) space.
 * 
 * Approach: Bottom-up merge sort on linked list (iterative to achieve O(1) space).
 * Here we show top-down for clarity (O(log n) stack space).
 * 
 * Time Complexity: O(n log n)
 * Space Complexity: O(log n) for recursion stack
 * 
 * Production Analogy: Sorting streaming data chunks in a pipeline where random access
 * is not available (like sorting log entries from a network stream).
 */
public class Problem17_SortList {
    
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int val) { this.val = val; }
    }
    
    public ListNode sortList(ListNode head) {
        if (head == null || head.next == null) return head;
        
        // Split into two halves
        ListNode slow = head, fast = head.next;
        while (fast != null && fast.next != null) {
            slow = slow.next;
            fast = fast.next.next;
        }
        ListNode mid = slow.next;
        slow.next = null;
        
        ListNode left = sortList(head);
        ListNode right = sortList(mid);
        return merge(left, right);
    }
    
    private ListNode merge(ListNode l1, ListNode l2) {
        ListNode dummy = new ListNode(0), curr = dummy;
        while (l1 != null && l2 != null) {
            if (l1.val <= l2.val) { curr.next = l1; l1 = l1.next; }
            else { curr.next = l2; l2 = l2.next; }
            curr = curr.next;
        }
        curr.next = (l1 != null) ? l1 : l2;
        return dummy.next;
    }
    
    private static String listToString(ListNode head) {
        StringBuilder sb = new StringBuilder("[");
        while (head != null) { sb.append(head.val); if (head.next != null) sb.append(","); head = head.next; }
        return sb.append("]").toString();
    }
    
    private static ListNode arrayToList(int[] arr) {
        ListNode dummy = new ListNode(0), curr = dummy;
        for (int v : arr) { curr.next = new ListNode(v); curr = curr.next; }
        return dummy.next;
    }
    
    public static void main(String[] args) {
        Problem17_SortList sol = new Problem17_SortList();
        
        System.out.println("Test 1: " + listToString(sol.sortList(arrayToList(new int[]{4,2,1,3})))); // [1,2,3,4]
        System.out.println("Test 2: " + listToString(sol.sortList(arrayToList(new int[]{-1,5,3,4,0})))); // [-1,0,3,4,5]
        System.out.println("Test 3: " + listToString(sol.sortList(null))); // []
        System.out.println("Test 4: " + listToString(sol.sortList(arrayToList(new int[]{1})))); // [1]
    }
}
