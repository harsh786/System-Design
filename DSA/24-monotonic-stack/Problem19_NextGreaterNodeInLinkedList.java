import java.util.*;

/**
 * Problem 19: Next Greater Node In Linked List (LeetCode 1019)
 * 
 * For each node in linked list, find next node with greater value.
 * 
 * Approach: Convert to array or process with index tracking.
 * Use decreasing monotonic stack.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Event stream processing - for each event, find the next
 * event that exceeds its severity level.
 */
public class Problem19_NextGreaterNodeInLinkedList {
    
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int v) { val = v; }
    }
    
    public int[] nextLargerNodes(ListNode head) {
        List<Integer> vals = new ArrayList<>();
        for (ListNode cur = head; cur != null; cur = cur.next) vals.add(cur.val);
        
        int n = vals.size();
        int[] result = new int[n];
        Deque<Integer> stack = new ArrayDeque<>();
        
        for (int i = 0; i < n; i++) {
            while (!stack.isEmpty() && vals.get(stack.peek()) < vals.get(i)) {
                result[stack.pop()] = vals.get(i);
            }
            stack.push(i);
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem19_NextGreaterNodeInLinkedList sol = new Problem19_NextGreaterNodeInLinkedList();
        
        // [2,1,5]
        ListNode h1 = new ListNode(2);
        h1.next = new ListNode(1);
        h1.next.next = new ListNode(5);
        System.out.println(Arrays.toString(sol.nextLargerNodes(h1))); // [5,5,0]
        
        // [2,7,4,3,5]
        ListNode h2 = new ListNode(2);
        h2.next = new ListNode(7);
        h2.next.next = new ListNode(4);
        h2.next.next.next = new ListNode(3);
        h2.next.next.next.next = new ListNode(5);
        System.out.println(Arrays.toString(sol.nextLargerNodes(h2))); // [7,0,5,5,0]
    }
}
