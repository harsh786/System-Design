/**
 * Problem 1: Reverse Linked List
 * 
 * Approach: Iterative pointer reversal. Maintain prev, curr, next pointers.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Like reversing the order of a deployment pipeline rollback chain -
 * each step now points to its predecessor instead of successor.
 */
public class Problem01_ReverseLinkedList {
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode reverseList(ListNode head) {
        ListNode prev = null, curr = head;
        while (curr != null) {
            ListNode next = curr.next;
            curr.next = prev;
            prev = curr;
            curr = next;
        }
        return prev;
    }

    static String toString(ListNode head) {
        StringBuilder sb = new StringBuilder();
        while (head != null) { sb.append(head.val).append("->"); head = head.next; }
        sb.append("null");
        return sb.toString();
    }

    public static void main(String[] args) {
        // Test 1: Normal list
        ListNode h1 = new ListNode(1, new ListNode(2, new ListNode(3, new ListNode(4, new ListNode(5)))));
        System.out.println("Test1: " + toString(reverseList(h1))); // 5->4->3->2->1->null

        // Test 2: Single node
        ListNode h2 = new ListNode(1);
        System.out.println("Test2: " + toString(reverseList(h2))); // 1->null

        // Test 3: Null
        System.out.println("Test3: " + toString(reverseList(null))); // null

        // Test 4: Two nodes
        ListNode h4 = new ListNode(1, new ListNode(2));
        System.out.println("Test4: " + toString(reverseList(h4))); // 2->1->null
    }
}
