/**
 * Problem 7: Add Two Numbers (digits stored in reverse order)
 * 
 * Approach: Traverse both lists simultaneously, sum digits + carry.
 * Time Complexity: O(max(m,n))
 * Space Complexity: O(max(m,n))
 * 
 * Production Analogy: Like aggregating distributed counters where each node holds
 * a partial sum that propagates overflow to the next partition.
 */
public class Problem07_AddTwoNumbers {
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode addTwoNumbers(ListNode l1, ListNode l2) {
        ListNode dummy = new ListNode(0), curr = dummy;
        int carry = 0;
        while (l1 != null || l2 != null || carry != 0) {
            int sum = carry;
            if (l1 != null) { sum += l1.val; l1 = l1.next; }
            if (l2 != null) { sum += l2.val; l2 = l2.next; }
            carry = sum / 10;
            curr.next = new ListNode(sum % 10);
            curr = curr.next;
        }
        return dummy.next;
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        // 342 + 465 = 807
        ListNode l1 = new ListNode(2, new ListNode(4, new ListNode(3)));
        ListNode l2 = new ListNode(5, new ListNode(6, new ListNode(4)));
        System.out.println("Test1: " + toString(addTwoNumbers(l1, l2))); // 7->0->8->null

        // 99 + 1 = 100
        ListNode l3 = new ListNode(9, new ListNode(9));
        ListNode l4 = new ListNode(1);
        System.out.println("Test2: " + toString(addTwoNumbers(l3, l4))); // 0->0->1->null
    }
}
