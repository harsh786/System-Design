/**
 * Problem 6: Reorder List (LeetCode 143)
 * 
 * Approach: 1) Find middle 2) Reverse second half 3) Merge alternating
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Load balancing requests by interleaving hot and cold partition
 * data to ensure even distribution across processing nodes.
 */
public class Problem06_ReorderList {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
    }

    public static void reorderList(ListNode head) {
        if (head == null || head.next == null) return;
        // Find middle
        ListNode slow = head, fast = head;
        while (fast.next != null && fast.next.next != null) { slow = slow.next; fast = fast.next.next; }
        // Reverse second half
        ListNode prev = null, curr = slow.next;
        slow.next = null;
        while (curr != null) { ListNode next = curr.next; curr.next = prev; prev = curr; curr = next; }
        // Merge
        ListNode first = head, second = prev;
        while (second != null) {
            ListNode tmp1 = first.next, tmp2 = second.next;
            first.next = second; second.next = tmp1;
            first = tmp1; second = tmp2;
        }
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
        ListNode l1 = buildList(1,2,3,4); reorderList(l1);
        System.out.println(listToString(l1)); // 1->4->2->3->null
        ListNode l2 = buildList(1,2,3,4,5); reorderList(l2);
        System.out.println(listToString(l2)); // 1->5->2->4->3->null
        ListNode l3 = buildList(1); reorderList(l3);
        System.out.println(listToString(l3)); // 1->null
    }
}
