/**
 * Problem 30: Rotate List
 * 
 * Rotate the list to the right by k places.
 * 
 * Approach: Find length, connect tail to head (circular), break at n-k%n position.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like rotating a circular buffer's read pointer by k
 * positions to change the consumption offset.
 */
public class Problem30_RotateList {
    static class ListNode {
        int val; ListNode next;
        ListNode(int v) { val = v; }
    }

    public static ListNode rotateRight(ListNode head, int k) {
        if (head == null || head.next == null || k == 0) return head;
        int len = 1;
        ListNode tail = head;
        while (tail.next != null) { tail = tail.next; len++; }
        k = k % len;
        if (k == 0) return head;
        tail.next = head; // make circular
        int stepsToNewTail = len - k;
        ListNode newTail = head;
        for (int i = 1; i < stepsToNewTail; i++) newTail = newTail.next;
        ListNode newHead = newTail.next;
        newTail.next = null;
        return newHead;
    }

    public static void main(String[] args) {
        ListNode h = new ListNode(1); h.next = new ListNode(2); h.next.next = new ListNode(3);
        h.next.next.next = new ListNode(4); h.next.next.next.next = new ListNode(5);
        ListNode r = rotateRight(h, 2);
        while (r != null) { System.out.print(r.val + " "); r = r.next; } // 4 5 1 2 3
        System.out.println();
    }
}
