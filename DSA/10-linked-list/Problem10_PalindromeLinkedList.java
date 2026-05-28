/**
 * Problem 10: Palindrome Linked List
 * 
 * Approach: Find middle, reverse second half, compare both halves.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Validating message integrity by comparing the first half
 * of a checksum stream with the reversed second half.
 */
public class Problem10_PalindromeLinkedList {
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static boolean isPalindrome(ListNode head) {
        if (head == null || head.next == null) return true;
        ListNode slow = head, fast = head;
        while (fast.next != null && fast.next.next != null) { slow = slow.next; fast = fast.next.next; }
        ListNode prev = null, curr = slow.next;
        while (curr != null) { ListNode next = curr.next; curr.next = prev; prev = curr; curr = next; }
        ListNode p1 = head, p2 = prev;
        while (p2 != null) {
            if (p1.val != p2.val) return false;
            p1 = p1.next; p2 = p2.next;
        }
        return true;
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(1, new ListNode(2, new ListNode(2, new ListNode(1))));
        System.out.println("Test1: " + isPalindrome(h1)); // true

        ListNode h2 = new ListNode(1, new ListNode(2));
        System.out.println("Test2: " + isPalindrome(h2)); // false

        System.out.println("Test3: " + isPalindrome(new ListNode(1))); // true
    }
}
