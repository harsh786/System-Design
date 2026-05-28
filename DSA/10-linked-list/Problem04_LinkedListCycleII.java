/**
 * Problem 4: Linked List Cycle II (LeetCode 142)
 * 
 * Approach: Floyd's algorithm - after detecting cycle, reset one pointer to head.
 * Move both one step at a time; they meet at cycle start.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Finding the exact service in a circular dependency chain
 * where the loop begins - critical for breaking deadlocks in distributed transactions.
 */
public class Problem04_LinkedListCycleII {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
    }

    public static ListNode detectCycle(ListNode head) {
        ListNode slow = head, fast = head;
        while (fast != null && fast.next != null) {
            slow = slow.next;
            fast = fast.next.next;
            if (slow == fast) {
                slow = head;
                while (slow != fast) { slow = slow.next; fast = fast.next; }
                return slow;
            }
        }
        return null;
    }

    public static void main(String[] args) {
        // Test 1: Cycle at node with val 2
        ListNode n1 = new ListNode(3), n2 = new ListNode(2), n3 = new ListNode(0), n4 = new ListNode(-4);
        n1.next = n2; n2.next = n3; n3.next = n4; n4.next = n2;
        System.out.println(detectCycle(n1).val); // 2

        // Test 2: No cycle
        ListNode a = new ListNode(1); a.next = new ListNode(2);
        System.out.println(detectCycle(a)); // null

        // Test 3: Cycle at head
        ListNode s = new ListNode(1); ListNode s2 = new ListNode(2);
        s.next = s2; s2.next = s;
        System.out.println(detectCycle(s).val); // 1
    }
}
