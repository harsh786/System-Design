import java.util.*;

/**
 * Problem 18: Insertion Sort List
 * 
 * Sort a linked list using insertion sort.
 * 
 * Approach: Maintain a sorted portion, insert each node in correct position.
 * Time Complexity: O(n²)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Maintaining a sorted leaderboard where new scores arrive one at a time
 * and must be inserted in rank order.
 */
public class Problem18_InsertionSortList {
    
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int val) { this.val = val; }
    }
    
    public ListNode insertionSortList(ListNode head) {
        ListNode dummy = new ListNode(Integer.MIN_VALUE);
        ListNode curr = head;
        
        while (curr != null) {
            ListNode next = curr.next;
            // Find insertion point
            ListNode prev = dummy;
            while (prev.next != null && prev.next.val < curr.val) {
                prev = prev.next;
            }
            curr.next = prev.next;
            prev.next = curr;
            curr = next;
        }
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
        Problem18_InsertionSortList sol = new Problem18_InsertionSortList();
        
        System.out.println("Test 1: " + listToString(sol.insertionSortList(arrayToList(new int[]{4,2,1,3})))); // [1,2,3,4]
        System.out.println("Test 2: " + listToString(sol.insertionSortList(arrayToList(new int[]{-1,5,3,4,0})))); // [-1,0,3,4,5]
        System.out.println("Test 3: " + listToString(sol.insertionSortList(arrayToList(new int[]{1})))); // [1]
    }
}
