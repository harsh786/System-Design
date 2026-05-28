/**
 * Problem 47: Reverse Nodes in Even Length Groups
 * Groups are: 1 node, 2 nodes, 3 nodes, ... Reverse groups with even actual length.
 * 
 * Approach: Track group sizes, count actual nodes, reverse if even-length group.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Batch processing where even-sized batches need special
 * reordering for load distribution fairness.
 */
public class Problem47_ReverseNodesInEvenLengthGroups {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode reverseEvenLengthGroups(ListNode head) {
        ListNode prev = head;
        int groupLen = 2; // first group of 1 is never reversed
        while (prev.next != null) {
            // Count actual nodes in this group
            ListNode curr = prev;
            int count = 0;
            for (int i = 0; i < groupLen && curr.next != null; i++) { curr = curr.next; count++; }
            if (count % 2 == 0) {
                // Reverse 'count' nodes after prev
                ListNode currNode = prev.next, prevNode = null;
                ListNode tail = prev.next;
                for (int i = 0; i < count; i++) {
                    ListNode next = currNode.next;
                    currNode.next = prevNode;
                    prevNode = currNode;
                    currNode = next;
                }
                prev.next = prevNode;
                tail.next = currNode;
                prev = tail;
            } else {
                for (int i = 0; i < count; i++) prev = prev.next;
            }
            groupLen++;
        }
        return head;
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(5, new ListNode(2, new ListNode(6, new ListNode(3, new ListNode(9, new ListNode(1, new ListNode(7, new ListNode(3, new ListNode(8, new ListNode(4))))))))));
        System.out.println("Test1: " + toString(reverseEvenLengthGroups(h1)));
        // 5->6->2->3->9->1->4->8->3->7->null

        ListNode h2 = new ListNode(1, new ListNode(1, new ListNode(0, new ListNode(6))));
        System.out.println("Test2: " + toString(reverseEvenLengthGroups(h2)));
        // 1->0->1->6->null
    }
}
