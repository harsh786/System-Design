/**
 * Problem 9: Merge k Sorted Lists (LeetCode 23)
 * 
 * Approach: Min-heap (PriorityQueue) to always pick the smallest head among k lists.
 * Time: O(N log k) where N = total nodes, Space: O(k)
 * 
 * Production Analogy: K-way merge in distributed databases (like LSM-tree compaction
 * in Cassandra/RocksDB) merging sorted SSTables.
 */
import java.util.*;

public class Problem09_MergeKSortedLists {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
    }

    public static ListNode mergeKLists(ListNode[] lists) {
        PriorityQueue<ListNode> pq = new PriorityQueue<>((a, b) -> a.val - b.val);
        for (ListNode l : lists) if (l != null) pq.offer(l);
        ListNode dummy = new ListNode(0), curr = dummy;
        while (!pq.isEmpty()) {
            ListNode node = pq.poll();
            curr.next = node; curr = curr.next;
            if (node.next != null) pq.offer(node.next);
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
        ListNode[] lists = {buildList(1,4,5), buildList(1,3,4), buildList(2,6)};
        System.out.println(listToString(mergeKLists(lists))); // 1->1->2->3->4->4->5->6->null
        System.out.println(listToString(mergeKLists(new ListNode[]{}))); // null
        System.out.println(listToString(mergeKLists(new ListNode[]{null}))); // null
    }
}
