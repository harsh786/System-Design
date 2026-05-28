/**
 * Problem 16: Palindrome Linked List
 * 
 * Check if a singly linked list is a palindrome.
 * 
 * Approach: Find middle with slow/fast, reverse second half, compare.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like verifying data integrity by comparing the first
 * half of a transmission with the reversed second half (mirror check).
 */
public class Problem16_PalindromeLinkedList {
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int v) { val = v; }
    }

    public static boolean isPalindrome(ListNode head) {
        if (head == null || head.next == null) return true;
        ListNode slow = head, fast = head;
        while (fast.next != null && fast.next.next != null) { slow = slow.next; fast = fast.next.next; }
        ListNode secondHalf = reverse(slow.next);
        ListNode p1 = head, p2 = secondHalf;
        while (p2 != null) {
            if (p1.val != p2.val) return false;
            p1 = p1.next; p2 = p2.next;
        }
        return true;
    }

    private static ListNode reverse(ListNode head) {
        ListNode prev = null;
        while (head != null) { ListNode next = head.next; head.next = prev; prev = head; head = next; }
        return prev;
    }

    public static void main(String[] args) {
        ListNode h = new ListNode(1); h.next = new ListNode(2); h.next.next = new ListNode(2); h.next.next.next = new ListNode(1);
        System.out.println(isPalindrome(h)); // true

        ListNode h2 = new ListNode(1); h2.next = new ListNode(2);
        System.out.println(isPalindrome(h2)); // false
    }
}
