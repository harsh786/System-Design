/**
 * Problem 31: Remove Linked List Elements - Remove all nodes with given value
 * 
 * Approach: Dummy head, skip nodes matching val.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Filtering out poisoned messages from a queue by value.
 */
public class Problem31_RemoveLinkedListElements {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode removeElements(ListNode head, int val) {
        ListNode dummy = new ListNode(0, head), curr = dummy;
        while (curr.next != null) {
            if (curr.next.val == val) curr.next = curr.next.next;
            else curr = curr.next;
        }
        return dummy.next;
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(1, new ListNode(2, new ListNode(6, new ListNode(3, new ListNode(4, new ListNode(5, new ListNode(6)))))));
        System.out.println("Test1: " + toString(removeElements(h1, 6))); // 1->2->3->4->5->null

        System.out.println("Test2: " + toString(removeElements(null, 1))); // null

        ListNode h3 = new ListNode(7, new ListNode(7, new ListNode(7)));
        System.out.println("Test3: " + toString(removeElements(h3, 7))); // null
    }
}
