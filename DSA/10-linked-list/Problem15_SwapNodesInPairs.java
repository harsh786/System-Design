/**
 * Problem 15: Swap Nodes in Pairs
 * 
 * Approach: Iterative - use dummy node, swap pairs by adjusting pointers.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Like swapping primary/secondary roles in a paired failover
 * cluster during scheduled maintenance.
 */
public class Problem15_SwapNodesInPairs {
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode swapPairs(ListNode head) {
        ListNode dummy = new ListNode(0, head), prev = dummy;
        while (prev.next != null && prev.next.next != null) {
            ListNode first = prev.next, second = prev.next.next;
            first.next = second.next;
            second.next = first;
            prev.next = second;
            prev = first;
        }
        return dummy.next;
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(1, new ListNode(2, new ListNode(3, new ListNode(4))));
        System.out.println("Test1: " + toString(swapPairs(h1))); // 2->1->4->3->null

        ListNode h2 = new ListNode(1);
        System.out.println("Test2: " + toString(swapPairs(h2))); // 1->null

        System.out.println("Test3: " + toString(swapPairs(null))); // null
    }
}
