/**
 * Problem 32: Convert Binary Number in a Linked List to Integer
 * 
 * Approach: Traverse, shift result left and OR with current bit.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Parsing a bitstream header where each node is a bit
 * in network packet processing.
 */
public class Problem32_ConvertBinaryNumberInLinkedList {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }

    public static int getDecimalValue(ListNode head) {
        int result = 0;
        while (head != null) {
            result = (result << 1) | head.val;
            head = head.next;
        }
        return result;
    }

    public static void main(String[] args) {
        ListNode h1 = new ListNode(1, new ListNode(0, new ListNode(1))); // 101 = 5
        System.out.println("Test1: " + getDecimalValue(h1)); // 5

        ListNode h2 = new ListNode(0);
        System.out.println("Test2: " + getDecimalValue(h2)); // 0

        ListNode h3 = new ListNode(1, new ListNode(1, new ListNode(1))); // 111 = 7
        System.out.println("Test3: " + getDecimalValue(h3)); // 7
    }
}
