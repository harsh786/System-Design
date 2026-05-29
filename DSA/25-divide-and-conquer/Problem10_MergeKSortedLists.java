import java.util.*;

/**
 * Problem 10: Merge k Sorted Lists (LeetCode 23)
 * 
 * D&C Approach:
 * - DIVIDE: Split k lists into two groups of k/2
 * - CONQUER: Recursively merge each group
 * - COMBINE: Merge the two resulting sorted lists
 * 
 * Recurrence: T(k) = 2T(k/2) + O(n) where n = total elements
 * Time: O(n log k), Space: O(log k) recursion
 * 
 * Production Analogy:
 * - K-way merge in LSM-tree compaction (RocksDB, LevelDB)
 * - Merging sorted results from multiple database shards
 * - Fan-in merge in external sort (merge phase)
 */
public class Problem10_MergeKSortedLists {

    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
    }

    public static ListNode mergeKLists(ListNode[] lists) {
        if (lists == null || lists.length == 0) return null;
        return mergeDC(lists, 0, lists.length - 1);
    }

    private static ListNode mergeDC(ListNode[] lists, int lo, int hi) {
        if (lo == hi) return lists[lo];
        int mid = lo + (hi - lo) / 2;
        ListNode left = mergeDC(lists, lo, mid);
        ListNode right = mergeDC(lists, mid + 1, hi);
        return mergeTwo(left, right);
    }

    private static ListNode mergeTwo(ListNode l1, ListNode l2) {
        ListNode dummy = new ListNode(0), curr = dummy;
        while (l1 != null && l2 != null) {
            if (l1.val <= l2.val) { curr.next = l1; l1 = l1.next; }
            else { curr.next = l2; l2 = l2.next; }
            curr = curr.next;
        }
        curr.next = (l1 != null) ? l1 : l2;
        return dummy.next;
    }

    private static ListNode build(int[] arr) {
        ListNode dummy = new ListNode(0), c = dummy;
        for (int v : arr) { c.next = new ListNode(v); c = c.next; }
        return dummy.next;
    }

    private static String toString(ListNode h) {
        StringBuilder sb = new StringBuilder("[");
        while (h != null) { sb.append(h.val); if (h.next != null) sb.append(","); h = h.next; }
        return sb.append("]").toString();
    }

    public static void main(String[] args) {
        ListNode[] lists = {build(new int[]{1,4,5}), build(new int[]{1,3,4}), build(new int[]{2,6})};
        System.out.println(toString(mergeKLists(lists))); // [1,1,2,3,4,4,5,6]
        System.out.println(toString(mergeKLists(new ListNode[]{}))); // []
        System.out.println(toString(mergeKLists(new ListNode[]{null}))); // []
        ListNode[] single = {build(new int[]{1,2,3})};
        System.out.println(toString(mergeKLists(single))); // [1,2,3]
    }
}
