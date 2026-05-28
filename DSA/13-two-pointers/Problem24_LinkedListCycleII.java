/**
 * Problem 24: Linked List Cycle II
 * 
 * Find the node where the cycle begins.
 * 
 * Approach: Floyd's algorithm - after meeting, reset one pointer to head.
 * Both move at speed 1; they meet at cycle start.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like identifying the exact service in a circular
 * dependency chain where the loop originates.
 */
public class Problem24_LinkedListCycleII {
    static class ListNode {
        int val; ListNode next;
        ListNode(int v) { val = v; }
    }

    public static ListNode detectCycle(ListNode head) {
        ListNode slow = head, fast = head;
        while (fast != null && fast.next != null) {
            slow = slow.next;
            fast = fast.next.next;
            if (slow == fast) {
                ListNode p = head;
                while (p != slow) { p = p.next; slow = slow.next; }
                return p;
            }
        }
        return null;
    }

    public static void main(String[] args) {
        ListNode n1 = new ListNode(3), n2 = new ListNode(2), n3 = new ListNode(0), n4 = new ListNode(-4);
        n1.next = n2; n2.next = n3; n3.next = n4; n4.next = n2;
        System.out.println(detectCycle(n1).val); // 2

        ListNode a = new ListNode(1);
        System.out.println(detectCycle(a)); // null
    }
}
