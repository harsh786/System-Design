/**
 * Problem 15: Linked List Cycle
 * 
 * Detect if a linked list has a cycle.
 * 
 * Approach: Floyd's slow/fast pointer. If they meet, cycle exists.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like detecting infinite redirect loops in HTTP -
 * one crawler moves at normal speed, another double speed; if they meet, loop exists.
 */
public class Problem15_LinkedListCycle {
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int v) { val = v; }
    }

    public static boolean hasCycle(ListNode head) {
        ListNode slow = head, fast = head;
        while (fast != null && fast.next != null) {
            slow = slow.next;
            fast = fast.next.next;
            if (slow == fast) return true;
        }
        return false;
    }

    public static void main(String[] args) {
        ListNode n1 = new ListNode(3), n2 = new ListNode(2), n3 = new ListNode(0), n4 = new ListNode(-4);
        n1.next = n2; n2.next = n3; n3.next = n4; n4.next = n2;
        System.out.println(hasCycle(n1)); // true

        ListNode a = new ListNode(1); a.next = new ListNode(2);
        System.out.println(hasCycle(a)); // false
    }
}
