/**
 * Problem 28: Split Linked List in Parts
 * 
 * Approach: Calculate size, distribute evenly with first (size%k) parts getting +1.
 * Time Complexity: O(n)
 * Space Complexity: O(k)
 * 
 * Production Analogy: Distributing work items evenly across k workers with
 * remainder items going to the first few workers.
 */
public class Problem28_SplitLinkedListInParts {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode[] splitListToParts(ListNode head, int k) {
        int len = 0;
        ListNode curr = head;
        while (curr != null) { len++; curr = curr.next; }
        int partSize = len / k, extra = len % k;
        ListNode[] result = new ListNode[k];
        curr = head;
        for (int i = 0; i < k && curr != null; i++) {
            result[i] = curr;
            int size = partSize + (i < extra ? 1 : 0);
            for (int j = 1; j < size; j++) curr = curr.next;
            ListNode next = curr.next;
            curr.next = null;
            curr = next;
        }
        return result;
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder("[");
        while (h != null) { sb.append(h.val); if(h.next!=null) sb.append(","); h = h.next; }
        sb.append("]"); return sb.toString();
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(1, new ListNode(2, new ListNode(3, new ListNode(4, new ListNode(5, new ListNode(6, new ListNode(7, new ListNode(8, new ListNode(9, new ListNode(10))))))))));
        ListNode[] parts = splitListToParts(h1, 3);
        for (ListNode p : parts) System.out.print(toString(p) + " ");
        System.out.println();

        ListNode h2 = new ListNode(1, new ListNode(2, new ListNode(3)));
        ListNode[] parts2 = splitListToParts(h2, 5);
        for (ListNode p : parts2) System.out.print(toString(p) + " ");
        System.out.println();
    }
}
