/**
 * Problem 3: Linked List Cycle (LeetCode 141)
 * 
 * Approach: Floyd's Tortoise and Hare - slow moves 1 step, fast moves 2 steps.
 * If they meet, there's a cycle.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Detecting circular dependencies in microservice call graphs
 * or deadlock detection in distributed systems.
 */
public class Problem03_LinkedListCycle {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
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
        // Test 1: Has cycle
        ListNode n1 = new ListNode(3), n2 = new ListNode(2), n3 = new ListNode(0), n4 = new ListNode(-4);
        n1.next = n2; n2.next = n3; n3.next = n4; n4.next = n2;
        System.out.println(hasCycle(n1)); // true

        // Test 2: No cycle
        ListNode a = new ListNode(1); a.next = new ListNode(2);
        System.out.println(hasCycle(a)); // false

        // Test 3: Single node no cycle
        System.out.println(hasCycle(new ListNode(1))); // false

        // Test 4: Single node with cycle
        ListNode s = new ListNode(1); s.next = s;
        System.out.println(hasCycle(s)); // true

        // Test 5: Null
        System.out.println(hasCycle(null)); // false
    }
}
