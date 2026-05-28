import java.util.*;

/**
 * Problem 4: Merge K Sorted Lists (LeetCode 23)
 * 
 * Approach: Use min-heap to always pick the smallest node among K list heads.
 * 
 * Time Complexity: O(N log K) where N = total nodes
 * Space Complexity: O(K)
 * 
 * Production Analogy: Merging sorted log streams from K microservices into a
 * single chronologically ordered event stream for centralized logging.
 */
public class Problem04_MergeKSortedLists {
    
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int v) { val = v; }
    }
    
    public ListNode mergeKLists(ListNode[] lists) {
        PriorityQueue<ListNode> pq = new PriorityQueue<>(Comparator.comparingInt(a -> a.val));
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
        Problem04_MergeKSortedLists sol = new Problem04_MergeKSortedLists();
        
        ListNode l1 = new ListNode(1); l1.next = new ListNode(4); l1.next.next = new ListNode(5);
        ListNode l2 = new ListNode(1); l2.next = new ListNode(3); l2.next.next = new ListNode(4);
        ListNode l3 = new ListNode(2); l3.next = new ListNode(6);
        
        ListNode result = sol.mergeKLists(new ListNode[]{l1, l2, l3});
        StringBuilder sb = new StringBuilder();
        while (result != null) { sb.append(result.val).append(" "); result = result.next; }
        System.out.println(sb.toString().trim()); // 1 1 2 3 4 4 5 6
        
        // Empty lists
        System.out.println(sol.mergeKLists(new ListNode[]{null, null})); // null
    }
}
