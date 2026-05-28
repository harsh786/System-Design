/**
 * Problem 19: Partition List - nodes less than x before nodes >= x
 * 
 * Approach: Two dummy lists (less, greater), merge at end.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Like routing high-priority vs low-priority traffic into
 * separate queues then concatenating for processing.
 */
public class Problem19_PartitionList {
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode partition(ListNode head, int x) {
        ListNode lessD = new ListNode(0), greaterD = new ListNode(0);
        ListNode less = lessD, greater = greaterD;
        while (head != null) {
            if (head.val < x) { less.next = head; less = less.next; }
            else { greater.next = head; greater = greater.next; }
            head = head.next;
        }
        greater.next = null;
        less.next = greaterD.next;
        return lessD.next;
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(1, new ListNode(4, new ListNode(3, new ListNode(2, new ListNode(5, new ListNode(2))))));
        System.out.println("Test1: " + toString(partition(h1, 3))); // 1->2->2->4->3->5->null

        ListNode h2 = new ListNode(2, new ListNode(1));
        System.out.println("Test2: " + toString(partition(h2, 2))); // 1->2->null
    }
}
