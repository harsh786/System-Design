import java.util.*;

/**
 * Problem 42: Remove Nodes From Linked List (LeetCode 2487)
 * 
 * Remove every node that has a greater node to its right.
 * 
 * Approach: Use monotonic decreasing stack (from values). Or reverse, build
 * increasing from right.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Pruning redundant cache entries where a later entry
 * supersedes earlier ones.
 */
public class Problem42_RemoveNodesFromLinkedList {
    
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int v) { val = v; }
    }
    
    public ListNode removeNodes(ListNode head) {
        Deque<ListNode> stack = new ArrayDeque<>();
        
        for (ListNode cur = head; cur != null; cur = cur.next) {
            while (!stack.isEmpty() && stack.peek().val < cur.val) {
                stack.pop();
            }
            stack.push(cur);
        }
        
        ListNode dummy = new ListNode(0);
        ListNode prev = dummy;
        // Stack has nodes in reverse order of result
        ListNode[] arr = stack.toArray(new ListNode[0]);
        for (int i = arr.length - 1; i >= 0; i--) {
            prev.next = arr[i];
            prev = arr[i];
        }
        prev.next = null;
        return dummy.next;
    }
    
    public static void main(String[] args) {
        Problem42_RemoveNodesFromLinkedList sol = new Problem42_RemoveNodesFromLinkedList();
        
        // [5,2,13,3,8] -> [13,8]
        ListNode h = new ListNode(5);
        h.next = new ListNode(2);
        h.next.next = new ListNode(13);
        h.next.next.next = new ListNode(3);
        h.next.next.next.next = new ListNode(8);
        
        ListNode res = sol.removeNodes(h);
        while (res != null) { System.out.print(res.val + " "); res = res.next; }
        System.out.println(); // 13 8
    }
}
