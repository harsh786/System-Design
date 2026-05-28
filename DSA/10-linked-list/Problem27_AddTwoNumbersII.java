/**
 * Problem 27: Add Two Numbers II (digits in normal order, most significant first)
 * 
 * Approach: Use stacks to process from least significant digit.
 * Time Complexity: O(m + n)
 * Space Complexity: O(m + n)
 * 
 * Production Analogy: Like adding two large distributed counters stored as
 * digit arrays across shards, needing carry propagation.
 */
import java.util.*;

public class Problem27_AddTwoNumbersII {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode addTwoNumbers(ListNode l1, ListNode l2) {
        Deque<Integer> s1 = new ArrayDeque<>(), s2 = new ArrayDeque<>();
        while (l1 != null) { s1.push(l1.val); l1 = l1.next; }
        while (l2 != null) { s2.push(l2.val); l2 = l2.next; }
        ListNode head = null;
        int carry = 0;
        while (!s1.isEmpty() || !s2.isEmpty() || carry != 0) {
            int sum = carry;
            if (!s1.isEmpty()) sum += s1.pop();
            if (!s2.isEmpty()) sum += s2.pop();
            carry = sum / 10;
            ListNode node = new ListNode(sum % 10);
            node.next = head;
            head = node;
        }
        return head;
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        // 7243 + 564 = 7807
        ListNode l1 = new ListNode(7, new ListNode(2, new ListNode(4, new ListNode(3))));
        ListNode l2 = new ListNode(5, new ListNode(6, new ListNode(4)));
        System.out.println("Test1: " + toString(addTwoNumbers(l1, l2))); // 7->8->0->7->null

        ListNode l3 = new ListNode(0), l4 = new ListNode(0);
        System.out.println("Test2: " + toString(addTwoNumbers(l3, l4))); // 0->null
    }
}
