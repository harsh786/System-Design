/**
 * Problem 29: Linked List Components - Count connected components in subset G
 * 
 * Approach: Traverse list, count transitions from "in set" to "not in set".
 * Time Complexity: O(n)
 * Space Complexity: O(|G|)
 * 
 * Production Analogy: Counting contiguous healthy segments in a service chain
 * where some services are marked as degraded.
 */
import java.util.*;

public class Problem29_LinkedListComponents {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static int numComponents(ListNode head, int[] nums) {
        Set<Integer> set = new HashSet<>();
        for (int n : nums) set.add(n);
        int count = 0;
        ListNode curr = head;
        while (curr != null) {
            if (set.contains(curr.val) && (curr.next == null || !set.contains(curr.next.val)))
                count++;
            curr = curr.next;
        }
        return count;
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(0, new ListNode(1, new ListNode(2, new ListNode(3))));
        System.out.println("Test1: " + numComponents(h1, new int[]{0, 1, 3})); // 2

        ListNode h2 = new ListNode(0, new ListNode(1, new ListNode(2, new ListNode(3, new ListNode(4)))));
        System.out.println("Test2: " + numComponents(h2, new int[]{0, 3, 1, 4})); // 2
    }
}
