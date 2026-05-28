/**
 * Problem 26: Reverse Linked List II - Reverse from position left to right
 * 
 * Approach: Navigate to position left-1, reverse the sublist, reconnect.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Like reversing a specific segment of a deployment pipeline
 * for targeted rollback without affecting the rest.
 */
public class Problem26_ReverseLinkedListII {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode reverseBetween(ListNode head, int left, int right) {
        ListNode dummy = new ListNode(0, head), prev = dummy;
        for (int i = 0; i < left - 1; i++) prev = prev.next;
        ListNode curr = prev.next;
        for (int i = 0; i < right - left; i++) {
            ListNode next = curr.next;
            curr.next = next.next;
            next.next = prev.next;
            prev.next = next;
        }
        return dummy.next;
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(1, new ListNode(2, new ListNode(3, new ListNode(4, new ListNode(5)))));
        System.out.println("Test1: " + toString(reverseBetween(h1, 2, 4))); // 1->4->3->2->5->null

        ListNode h2 = new ListNode(5);
        System.out.println("Test2: " + toString(reverseBetween(h2, 1, 1))); // 5->null
    }
}
