import java.util.*;

/**
 * Problem 3: Linked List Random Node (LeetCode 382)
 * 
 * Given a singly linked list, return a random node's value.
 * Each node must have the same probability of being chosen.
 * 
 * Constraint: The linked list might be very large (unknown size).
 * You must solve it without knowing the size upfront.
 * 
 * This is a direct application of reservoir sampling with k=1.
 */
public class Problem03_LinkedListRandomNode {

    static class ListNode {
        int val;
        ListNode next;
        ListNode(int val) { this.val = val; }
    }

    private ListNode head;
    private Random rand;

    public Problem03_LinkedListRandomNode(ListNode head) {
        this.head = head;
        this.rand = new Random();
    }

    /** Returns a random node's value using reservoir sampling */
    public int getRandom() {
        ListNode current = head;
        int result = current.val;
        int i = 1;
        current = current.next;
        
        while (current != null) {
            i++;
            // Replace with probability 1/i
            if (rand.nextInt(i) == 0) {
                result = current.val;
            }
            current = current.next;
        }
        return result;
    }

    public static void main(String[] args) {
        // Build linked list: 1 -> 2 -> 3 -> 4 -> 5
        ListNode head = new ListNode(1);
        ListNode curr = head;
        for (int i = 2; i <= 5; i++) {
            curr.next = new ListNode(i);
            curr = curr.next;
        }

        Problem03_LinkedListRandomNode solution = new Problem03_LinkedListRandomNode(head);
        
        // Test uniformity
        int trials = 100000;
        Map<Integer, Integer> freq = new HashMap<>();
        for (int t = 0; t < trials; t++) {
            int val = solution.getRandom();
            freq.merge(val, 1, Integer::sum);
        }

        System.out.println("LeetCode 382: Linked List Random Node");
        System.out.println("List: 1 -> 2 -> 3 -> 4 -> 5");
        System.out.println("Expected: 20% each\n");
        for (int i = 1; i <= 5; i++) {
            System.out.printf("  Node %d: %.2f%%%n", i, 100.0 * freq.getOrDefault(i, 0) / trials);
        }
    }
}
