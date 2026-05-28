/**
 * Problem 43: Merge In Between Linked Lists
 * Remove nodes from a to b in list1, insert list2 in that gap.
 * 
 * Approach: Find node at (a-1) and (b+1), connect list2 between them.
 * Time Complexity: O(n + m)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Hot-swapping a segment of a processing pipeline with
 * a replacement chain during live migration.
 */
public class Problem43_MergeInBetweenLinkedLists {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode mergeInBetween(ListNode list1, int a, int b, ListNode list2) {
        ListNode prev = list1;
        for (int i = 0; i < a - 1; i++) prev = prev.next;
        ListNode after = prev;
        for (int i = 0; i <= b - a + 1; i++) after = after.next;
        prev.next = list2;
        ListNode tail2 = list2;
        while (tail2.next != null) tail2 = tail2.next;
        tail2.next = after;
        return list1;
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        // list1: 0->1->2->3->4->5, a=3,b=4, list2: 1000000->1000001->1000002
        ListNode l1 = new ListNode(0, new ListNode(1, new ListNode(2, new ListNode(3, new ListNode(4, new ListNode(5))))));
        ListNode l2 = new ListNode(1000000, new ListNode(1000001, new ListNode(1000002)));
        System.out.println("Test1: " + toString(mergeInBetween(l1, 3, 4, l2)));
        // 0->1->2->1000000->1000001->1000002->5->null
    }
}
