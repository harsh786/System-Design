/**
 * Problem 10: Palindrome Linked List (LeetCode 234)
 * 
 * Approach: Find middle, reverse second half, compare both halves.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Verifying data integrity by comparing forward and backward
 * checksums in network packet validation.
 */
public class Problem10_PalindromeLinkedList {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
    }

    public static boolean isPalindrome(ListNode head) {
        if (head == null || head.next == null) return true;
        ListNode slow = head, fast = head;
        while (fast.next != null && fast.next.next != null) { slow = slow.next; fast = fast.next.next; }
        // Reverse second half
        ListNode prev = null, curr = slow.next;
        while (curr != null) { ListNode next = curr.next; curr.next = prev; prev = curr; curr = next; }
        // Compare
        ListNode p1 = head, p2 = prev;
        while (p2 != null) {
            if (p1.val != p2.val) return false;
            p1 = p1.next; p2 = p2.next;
        }
        return true;
    }

    static ListNode buildList(int... vals) {
        ListNode dummy = new ListNode(0), curr = dummy;
        for (int v : vals) { curr.next = new ListNode(v); curr = curr.next; }
        return dummy.next;
    }

    public static void main(String[] args) {
        System.out.println(isPalindrome(buildList(1,2,2,1))); // true
        System.out.println(isPalindrome(buildList(1,2))); // false
        System.out.println(isPalindrome(buildList(1,2,3,2,1))); // true
        System.out.println(isPalindrome(buildList(1))); // true
        System.out.println(isPalindrome(null)); // true
    }
}
