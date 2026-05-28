/**
 * Problem 4: Linked List Cycle II - Find the node where the cycle begins
 * 
 * Approach: Floyd's algorithm. After slow/fast meet, reset one pointer to head.
 * Move both at same speed - they meet at cycle start.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Identifying the exact service in a circular dependency chain
 * that initiates the loop, enabling targeted resolution.
 */
public class Problem04_LinkedListCycleII {
    static class ListNode {
        int val;
        ListNode next;
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
        ListNode n1 = new ListNode(3), n2 = new ListNode(2), n3 = new ListNode(0), n4 = new ListNode(-4);
        n1.next = n2; n2.next = n3; n3.next = n4; n4.next = n2;
        System.out.println("Test1: cycle starts at val=" + detectCycle(n1).val); // 2

        ListNode h2 = new ListNode(1); h2.next = new ListNode(2);
        System.out.println("Test2: " + detectCycle(h2)); // null

        System.out.println("Test3: " + detectCycle(null)); // null
    }
}
