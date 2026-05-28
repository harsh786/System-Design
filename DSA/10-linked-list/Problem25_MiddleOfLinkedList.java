/**
 * Problem 25: Middle of the Linked List
 * 
 * Approach: Slow/fast pointers. When fast reaches end, slow is at middle.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Finding the median partition point for load splitting
 * without knowing total request count upfront.
 */
public class Problem25_MiddleOfLinkedList {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode middleNode(ListNode head) {
        ListNode slow = head, fast = head;
        while (fast != null && fast.next != null) { slow = slow.next; fast = fast.next.next; }
        return slow;
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(1, new ListNode(2, new ListNode(3, new ListNode(4, new ListNode(5)))));
        System.out.println("Test1: " + middleNode(h1).val); // 3

        ListNode h2 = new ListNode(1, new ListNode(2, new ListNode(3, new ListNode(4, new ListNode(5, new ListNode(6))))));
        System.out.println("Test2: " + middleNode(h2).val); // 4

        System.out.println("Test3: " + middleNode(new ListNode(1)).val); // 1
    }
}
