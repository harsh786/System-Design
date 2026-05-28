/**
 * Problem 11: Intersection of Two Linked Lists (LeetCode 160)
 * 
 * Approach: Two pointers - when one reaches end, redirect to other list's head.
 * They meet at intersection or both become null.
 * Time: O(n+m), Space: O(1)
 * 
 * Production Analogy: Finding shared dependencies between two microservice call chains.
 */
public class Problem11_IntersectionOfTwoLinkedLists {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
    }

    public static ListNode getIntersectionNode(ListNode headA, ListNode headB) {
        ListNode a = headA, b = headB;
        while (a != b) {
            a = (a == null) ? headB : a.next;
            b = (b == null) ? headA : b.next;
        }
        return a;
    }

    public static void main(String[] args) {
        // Test 1: Intersection at node 8
        ListNode common = new ListNode(8); common.next = new ListNode(4); common.next.next = new ListNode(5);
        ListNode a = new ListNode(4); a.next = new ListNode(1); a.next.next = common;
        ListNode b = new ListNode(5); b.next = new ListNode(6); b.next.next = new ListNode(1); b.next.next.next = common;
        System.out.println(getIntersectionNode(a, b).val); // 8

        // Test 2: No intersection
        ListNode x = new ListNode(1); x.next = new ListNode(2);
        ListNode y = new ListNode(3); y.next = new ListNode(4);
        System.out.println(getIntersectionNode(x, y)); // null
    }
}
