/**
 * Problem 1: Reverse Linked List (LeetCode 206)
 * 
 * Approach: Iterative - maintain prev, curr, next pointers and reverse links one by one.
 * Time Complexity: O(n), Space Complexity: O(1)
 * 
 * Production Analogy: Like reversing a chain of microservice call dependencies
 * when refactoring from synchronous to event-driven architecture. Each service
 * (node) needs its "next dependency" pointer flipped.
 */
public class Problem01_ReverseLinkedList {
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    // Iterative approach
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

    // Recursive approach
    public static ListNode reverseListRecursive(ListNode head) {
        if (head == null || head.next == null) return head;
        ListNode newHead = reverseListRecursive(head.next);
        head.next.next = head;
        head.next = null;
        return newHead;
    }

    static String listToString(ListNode head) {
        StringBuilder sb = new StringBuilder();
        while (head != null) { sb.append(head.val).append("->"); head = head.next; }
        sb.append("null");
        return sb.toString();
    }

    static ListNode buildList(int... vals) {
        ListNode dummy = new ListNode(0);
        ListNode curr = dummy;
        for (int v : vals) { curr.next = new ListNode(v); curr = curr.next; }
        return dummy.next;
    }

    public static void main(String[] args) {
        // Test 1: Normal list
        System.out.println(listToString(reverseList(buildList(1,2,3,4,5)))); // 5->4->3->2->1->null
        // Test 2: Single node
        System.out.println(listToString(reverseList(buildList(1)))); // 1->null
        // Test 3: Empty list
        System.out.println(listToString(reverseList(null))); // null
        // Test 4: Two nodes
        System.out.println(listToString(reverseList(buildList(1,2)))); // 2->1->null
        // Test 5: Recursive
        System.out.println(listToString(reverseListRecursive(buildList(1,2,3)))); // 3->2->1->null
    }
}
