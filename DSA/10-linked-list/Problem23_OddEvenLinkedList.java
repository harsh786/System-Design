/**
 * Problem 23: Odd Even Linked List - Group odd-indexed then even-indexed nodes.
 * 
 * Approach: Maintain odd and even pointers, link odd list to even list's head.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Segregating A/B test traffic into separate processing lanes
 * while maintaining order within each group.
 */
public class Problem23_OddEvenLinkedList {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode oddEvenList(ListNode head) {
        if (head == null) return null;
        ListNode odd = head, even = head.next, evenHead = even;
        while (even != null && even.next != null) {
            odd.next = even.next; odd = odd.next;
            even.next = odd.next; even = even.next;
        }
        odd.next = evenHead;
        return head;
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(1, new ListNode(2, new ListNode(3, new ListNode(4, new ListNode(5)))));
        System.out.println("Test1: " + toString(oddEvenList(h1))); // 1->3->5->2->4->null

        ListNode h2 = new ListNode(2, new ListNode(1, new ListNode(3, new ListNode(5, new ListNode(6, new ListNode(4, new ListNode(7)))))));
        System.out.println("Test2: " + toString(oddEvenList(h2))); // 2->3->6->7->1->5->4->null
    }
}
