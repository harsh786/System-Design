/**
 * Problem 3: Linked List Cycle
 * 
 * Approach: Floyd's cycle detection - slow/fast pointers. If they meet, cycle exists.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Detecting infinite redirect loops in a web crawler or 
 * circular dependencies in a microservice dependency graph.
 */
public class Problem03_LinkedListCycle {
    static class ListNode {
        int val;
        ListNode next;
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
        // Test 1: Cycle exists
        ListNode n1 = new ListNode(3), n2 = new ListNode(2), n3 = new ListNode(0), n4 = new ListNode(-4);
        n1.next = n2; n2.next = n3; n3.next = n4; n4.next = n2;
        System.out.println("Test1 (cycle): " + hasCycle(n1)); // true

        // Test 2: No cycle
        ListNode h2 = new ListNode(1); h2.next = new ListNode(2);
        System.out.println("Test2 (no cycle): " + hasCycle(h2)); // false

        // Test 3: Single node no cycle
        System.out.println("Test3 (single): " + hasCycle(new ListNode(1))); // false

        // Test 4: Null
        System.out.println("Test4 (null): " + hasCycle(null)); // false
    }
}
