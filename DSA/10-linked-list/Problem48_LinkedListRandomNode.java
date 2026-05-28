/**
 * Problem 48: Linked List Random Node (Reservoir Sampling)
 * 
 * Approach: Reservoir sampling - each element has equal probability of being chosen.
 * For kth element, probability of selection = 1/k.
 * Time Complexity: O(n) per getRandom call
 * Space Complexity: O(1)
 * 
 * Production Analogy: Sampling from a data stream of unknown length for
 * real-time analytics without storing all elements.
 */
import java.util.Random;

public class Problem48_LinkedListRandomNode {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    static class Solution {
        ListNode head;
        Random rand = new Random();

        public Solution(ListNode head) { this.head = head; }

        public int getRandom() {
            ListNode curr = head;
            int result = curr.val;
            int i = 1;
            while (curr != null) {
                if (rand.nextInt(i) == 0) result = curr.val;
                curr = curr.next;
                i++;
            }
            return result;
        }
    }

    public static void main(String[] args) {
        ListNode h = new ListNode(1, new ListNode(2, new ListNode(3)));
        Solution sol = new Solution(h);
        // Run multiple times to show randomness
        int[] counts = new int[4];
        for (int i = 0; i < 3000; i++) counts[sol.getRandom()]++;
        System.out.println("1: " + counts[1] + ", 2: " + counts[2] + ", 3: " + counts[3]);
        // Each should be ~1000
    }
}
