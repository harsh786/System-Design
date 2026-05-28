/**
 * Problem 28: Intersection of Two Linked Lists
 * 
 * Find the node where two singly linked lists intersect.
 * 
 * Approach: Two pointers traverse both lists; on reaching end, switch to other list's head.
 * They meet at intersection or both reach null.
 * Time: O(m+n), Space: O(1)
 * 
 * Production Analogy: Like finding the common downstream service where two
 * different API call chains converge.
 */
public class Problem28_IntersectionOfTwoLinkedLists {
    static class ListNode {
        int val; ListNode next;
        ListNode(int v) { val = v; }
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
        ListNode common = new ListNode(8); common.next = new ListNode(10);
        ListNode a = new ListNode(1); a.next = new ListNode(2); a.next.next = common;
        ListNode b = new ListNode(3); b.next = common;
        System.out.println(getIntersectionNode(a, b).val); // 8

        ListNode x = new ListNode(1);
        ListNode y = new ListNode(2);
        System.out.println(getIntersectionNode(x, y)); // null
    }
}
