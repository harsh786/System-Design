public class Problem04_ReverseLinkedListRecursive {
    static class ListNode { int val; ListNode next; ListNode(int v) { val = v; } }
    public static ListNode reverseList(ListNode head) {
        if (head == null || head.next == null) return head;
        ListNode newHead = reverseList(head.next);
        head.next.next = head; head.next = null;
        return newHead;
    }
    public static void main(String[] args) {
        ListNode h = new ListNode(1); h.next = new ListNode(2); h.next.next = new ListNode(3);
        ListNode res = reverseList(h);
        while (res != null) { System.out.print(res.val + " "); res = res.next; } // 3 2 1
    }
}
