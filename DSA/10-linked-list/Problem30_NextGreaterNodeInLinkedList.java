/**
 * Problem 30: Next Greater Node In Linked List
 * 
 * Approach: Convert to array, use monotonic stack to find next greater element.
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like finding the next spike in a time-series monitoring
 * stream - each metric wants to know when it will be exceeded.
 */
import java.util.*;

public class Problem30_NextGreaterNodeInLinkedList {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static int[] nextLargerNodes(ListNode head) {
        List<Integer> list = new ArrayList<>();
        while (head != null) { list.add(head.val); head = head.next; }
        int[] result = new int[list.size()];
        Deque<Integer> stack = new ArrayDeque<>(); // stores indices
        for (int i = 0; i < list.size(); i++) {
            while (!stack.isEmpty() && list.get(stack.peek()) < list.get(i))
                result[stack.pop()] = list.get(i);
            stack.push(i);
        }
        return result;
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(2, new ListNode(1, new ListNode(5)));
        System.out.println("Test1: " + Arrays.toString(nextLargerNodes(h1))); // [5,5,0]

        ListNode h2 = new ListNode(2, new ListNode(7, new ListNode(4, new ListNode(3, new ListNode(5)))));
        System.out.println("Test2: " + Arrays.toString(nextLargerNodes(h2))); // [7,0,5,5,0]
    }
}
