/**
 * Problem 16: Reverse Nodes in k-Group
 * 
 * Approach: Count k nodes ahead, reverse that segment, connect to next group recursively.
 * Time Complexity: O(n)
 * Space Complexity: O(n/k) recursion stack
 * 
 * Production Analogy: Like batch processing pipeline - reverse the order within
 * each batch window for priority rebalancing.
 */
public class Problem16_ReverseNodesInKGroup {
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode reverseKGroup(ListNode head, int k) {
        ListNode curr = head;
        int count = 0;
        while (curr != null && count < k) { curr = curr.next; count++; }
        if (count < k) return head;
        ListNode prev = reverseKGroup(curr, k);
        curr = head;
        for (int i = 0; i < k; i++) {
            ListNode next = curr.next;
            curr.next = prev;
            prev = curr;
            curr = next;
        }
        return prev;
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(1, new ListNode(2, new ListNode(3, new ListNode(4, new ListNode(5)))));
        System.out.println("Test1 k=2: " + toString(reverseKGroup(h1, 2))); // 2->1->4->3->5->null

        ListNode h2 = new ListNode(1, new ListNode(2, new ListNode(3, new ListNode(4, new ListNode(5)))));
        System.out.println("Test2 k=3: " + toString(reverseKGroup(h2, 3))); // 3->2->1->4->5->null
    }
}
