/**
 * Problem 42: Swapping Nodes in a Linked List - Swap kth from start and kth from end
 * 
 * Approach: Find kth from start, then use two-pointer to find kth from end, swap values.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Swapping priority between the kth newest and kth oldest
 * items in a queue for rebalancing.
 */
public class Problem42_SwappingNodesInLinkedList {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode swapNodes(ListNode head, int k) {
        ListNode curr = head;
        for (int i = 1; i < k; i++) curr = curr.next;
        ListNode first = curr;
        ListNode slow = head;
        while (curr.next != null) { curr = curr.next; slow = slow.next; }
        // swap values
        int tmp = first.val; first.val = slow.val; slow.val = tmp;
        return head;
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(1, new ListNode(2, new ListNode(3, new ListNode(4, new ListNode(5)))));
        System.out.println("Test1: " + toString(swapNodes(h1, 2))); // 1->4->3->2->5->null

        ListNode h2 = new ListNode(7, new ListNode(9, new ListNode(6, new ListNode(6, new ListNode(7, new ListNode(8, new ListNode(3, new ListNode(0, new ListNode(9, new ListNode(5))))))))));
        System.out.println("Test2: " + toString(swapNodes(h2, 5)));
    }
}
