/**
 * Problem 41: Remove Zero Sum Consecutive Nodes from Linked List
 * 
 * Approach: Prefix sum with HashMap. If same prefix sum seen before, remove nodes between.
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Canceling out offsetting transactions in a ledger -
 * consecutive debits and credits that net to zero are collapsed.
 */
import java.util.*;

public class Problem41_RemoveZeroSumConsecutiveNodes {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode removeZeroSumSublists(ListNode head) {
        ListNode dummy = new ListNode(0, head);
        Map<Integer, ListNode> map = new HashMap<>();
        int prefix = 0;
        // First pass: record last occurrence of each prefix sum
        for (ListNode curr = dummy; curr != null; curr = curr.next) {
            prefix += curr.val;
            map.put(prefix, curr);
        }
        // Second pass: skip to last occurrence of same prefix sum
        prefix = 0;
        for (ListNode curr = dummy; curr != null; curr = curr.next) {
            prefix += curr.val;
            curr.next = map.get(prefix).next;
        }
        return dummy.next;
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(1, new ListNode(2, new ListNode(-3, new ListNode(3, new ListNode(1)))));
        System.out.println("Test1: " + toString(removeZeroSumSublists(h1))); // 3->1->null

        ListNode h2 = new ListNode(1, new ListNode(2, new ListNode(3, new ListNode(-3, new ListNode(-2)))));
        System.out.println("Test2: " + toString(removeZeroSumSublists(h2))); // 1->null
    }
}
