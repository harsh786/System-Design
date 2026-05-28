/**
 * Problem 7: Add Two Numbers (LeetCode 2)
 * 
 * Approach: Traverse both lists simultaneously, sum digits + carry, create new nodes.
 * Time: O(max(n,m)), Space: O(max(n,m))
 * 
 * Production Analogy: Arbitrary precision arithmetic in financial systems where
 * numbers exceed 64-bit limits (blockchain transaction amounts).
 */
public class Problem07_AddTwoNumbers {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
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

    static ListNode buildList(int... vals) {
        ListNode dummy = new ListNode(0), curr = dummy;
        for (int v : vals) { curr.next = new ListNode(v); curr = curr.next; }
        return dummy.next;
    }

    static String listToString(ListNode head) {
        StringBuilder sb = new StringBuilder();
        while (head != null) { sb.append(head.val).append("->"); head = head.next; }
        return sb.append("null").toString();
    }

    public static void main(String[] args) {
        System.out.println(listToString(addTwoNumbers(buildList(2,4,3), buildList(5,6,4)))); // 7->0->8->null (342+465=807)
        System.out.println(listToString(addTwoNumbers(buildList(0), buildList(0)))); // 0->null
        System.out.println(listToString(addTwoNumbers(buildList(9,9,9), buildList(1)))); // 0->0->0->1->null
    }
}
