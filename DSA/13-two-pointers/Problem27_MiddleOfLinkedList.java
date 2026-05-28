/**
 * Problem 27: Middle of the Linked List
 * 
 * Return the middle node (second middle if even length).
 * 
 * Approach: Slow moves 1 step, fast moves 2. When fast reaches end, slow is at middle.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like finding the median latency request in a sorted
 * request log without knowing total count upfront.
 */
public class Problem27_MiddleOfLinkedList {
    static class ListNode {
        int val; ListNode next;
        ListNode(int v) { val = v; }
    }

    public static ListNode middleNode(ListNode head) {
        ListNode slow = head, fast = head;
        while (fast != null && fast.next != null) { slow = slow.next; fast = fast.next.next; }
        return slow;
    }

    public static void main(String[] args) {
        ListNode h = new ListNode(1); h.next = new ListNode(2); h.next.next = new ListNode(3);
        h.next.next.next = new ListNode(4); h.next.next.next.next = new ListNode(5);
        System.out.println(middleNode(h).val); // 3

        h.next.next.next.next.next = new ListNode(6);
        System.out.println(middleNode(h).val); // 4
    }
}
