/**
 * Problem 46: Double a Number Represented as a Linked List
 * 
 * Approach: Reverse, double with carry, reverse back. Or recursive.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Scaling a distributed counter by 2x across partitions
 * with carry propagation between shards.
 */
public class Problem46_DoubleANumber {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode doubleIt(ListNode head) {
        // Reverse
        ListNode rev = reverse(head);
        ListNode curr = rev;
        int carry = 0;
        ListNode prev = null;
        while (curr != null) {
            int val = curr.val * 2 + carry;
            curr.val = val % 10;
            carry = val / 10;
            prev = curr;
            curr = curr.next;
        }
        if (carry > 0) prev.next = new ListNode(carry);
        return reverse(rev);
    }

    private static ListNode reverse(ListNode head) {
        ListNode prev = null, curr = head;
        while (curr != null) { ListNode next = curr.next; curr.next = prev; prev = curr; curr = next; }
        return prev;
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(1, new ListNode(8, new ListNode(9)));
        System.out.println("Test1: " + toString(doubleIt(h1))); // 3->7->8->null

        ListNode h2 = new ListNode(9, new ListNode(9, new ListNode(9)));
        System.out.println("Test2: " + toString(doubleIt(h2))); // 1->9->9->8->null
    }
}
