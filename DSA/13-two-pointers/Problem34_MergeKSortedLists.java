/**
 * Problem 34: Merge k Sorted Lists
 * 
 * Merge k sorted linked lists into one sorted list.
 * 
 * Approach: Min-heap (priority queue) of list heads; extract min, advance that list.
 * Time: O(N log k) where N = total nodes, Space: O(k)
 * 
 * Production Analogy: Like merging k sorted shards' results in a distributed
 * database query - priority queue selects next smallest across all shards.
 */
import java.util.PriorityQueue;

public class Problem34_MergeKSortedLists {
    static class ListNode {
        int val; ListNode next;
        ListNode(int v) { val = v; }
    }

    public static ListNode mergeKLists(ListNode[] lists) {
        PriorityQueue<ListNode> pq = new PriorityQueue<>((a, b) -> a.val - b.val);
        for (ListNode l : lists) if (l != null) pq.offer(l);
        ListNode dummy = new ListNode(0), curr = dummy;
        while (!pq.isEmpty()) {
            ListNode node = pq.poll();
            curr.next = node;
            curr = curr.next;
            if (node.next != null) pq.offer(node.next);
        }
        return dummy.next;
    }

    public static void main(String[] args) {
        ListNode l1 = new ListNode(1); l1.next = new ListNode(4); l1.next.next = new ListNode(5);
        ListNode l2 = new ListNode(1); l2.next = new ListNode(3); l2.next.next = new ListNode(4);
        ListNode l3 = new ListNode(2); l3.next = new ListNode(6);
        ListNode r = mergeKLists(new ListNode[]{l1, l2, l3});
        while (r != null) { System.out.print(r.val + " "); r = r.next; } // 1 1 2 3 4 4 5 6
        System.out.println();
    }
}
