/**
 * Problem 11: Intersection of Two Linked Lists
 * 
 * Approach: Two pointers - when one reaches end, redirect to other list's head.
 * They meet at intersection or both reach null.
 * Time Complexity: O(m + n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Finding the common downstream service where two different
 * request paths converge in a service mesh.
 */
public class Problem11_IntersectionOfTwoLinkedLists {
    static class ListNode {
        int val;
        ListNode next;
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
        ListNode common = new ListNode(8); common.next = new ListNode(4);
        ListNode a = new ListNode(4); a.next = new ListNode(1); a.next.next = common;
        ListNode b = new ListNode(5); b.next = new ListNode(6); b.next.next = new ListNode(1); b.next.next.next = common;
        System.out.println("Test1: " + getIntersectionNode(a, b).val); // 8

        ListNode c = new ListNode(1), d = new ListNode(2);
        System.out.println("Test2: " + getIntersectionNode(c, d)); // null
    }
}
