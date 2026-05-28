/**
 * Problem 45: Maximum Twin Sum of a Linked List
 * Twin: node i paired with node (n-1-i). Find max twin sum.
 * 
 * Approach: Find middle, reverse second half, pair and compute max sum.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Finding the maximum combined load between paired
 * primary/secondary servers in a mirrored deployment.
 */
public class Problem45_MaximumTwinSum {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static int pairSum(ListNode head) {
        ListNode slow = head, fast = head;
        while (fast != null && fast.next != null) { slow = slow.next; fast = fast.next.next; }
        // Reverse second half
        ListNode prev = null, curr = slow;
        while (curr != null) { ListNode next = curr.next; curr.next = prev; prev = curr; curr = next; }
        int max = 0;
        ListNode left = head, right = prev;
        while (right != null) { max = Math.max(max, left.val + right.val); left = left.next; right = right.next; }
        return max;
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(5, new ListNode(4, new ListNode(2, new ListNode(1))));
        System.out.println("Test1: " + pairSum(h1)); // 6

        ListNode h2 = new ListNode(4, new ListNode(2, new ListNode(2, new ListNode(3))));
        System.out.println("Test2: " + pairSum(h2)); // 7

        ListNode h3 = new ListNode(1, new ListNode(100000));
        System.out.println("Test3: " + pairSum(h3)); // 100001
    }
}
