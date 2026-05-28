/**
 * Problem 9: Merge k Sorted Lists
 * 
 * Approach: Min-heap (priority queue) holding one node from each list.
 * Time Complexity: O(N log k) where N = total nodes, k = number of lists
 * Space Complexity: O(k)
 * 
 * Production Analogy: Like a distributed merge-sort in MapReduce - each mapper
 * produces a sorted stream and the reducer merges them via priority queue.
 */
import java.util.*;

public class Problem09_MergeKSortedLists {
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static ListNode mergeKLists(ListNode[] lists) {
        PriorityQueue<ListNode> pq = new PriorityQueue<>((a, b) -> a.val - b.val);
        for (ListNode l : lists) if (l != null) pq.offer(l);
        ListNode dummy = new ListNode(0), tail = dummy;
        while (!pq.isEmpty()) {
            ListNode node = pq.poll();
            tail.next = node;
            tail = tail.next;
            if (node.next != null) pq.offer(node.next);
        }
        return dummy.next;
    }

    static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        ListNode[] lists = {
            new ListNode(1, new ListNode(4, new ListNode(5))),
            new ListNode(1, new ListNode(3, new ListNode(4))),
            new ListNode(2, new ListNode(6))
        };
        System.out.println("Test1: " + toString(mergeKLists(lists)));

        System.out.println("Test2: " + toString(mergeKLists(new ListNode[]{}))); // null
        System.out.println("Test3: " + toString(mergeKLists(new ListNode[]{null}))); // null
    }
}
