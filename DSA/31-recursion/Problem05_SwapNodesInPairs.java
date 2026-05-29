public class Problem05_SwapNodesInPairs {
    static class ListNode { int val; ListNode next; ListNode(int v) { val = v; } }
    public static ListNode swapPairs(ListNode head) {
        if (head == null || head.next == null) return head;
        ListNode second = head.next;
        head.next = swapPairs(second.next);
        second.next = head;
        return second;
    }
    public static void main(String[] args) {
        ListNode h = new ListNode(1); h.next = new ListNode(2); h.next.next = new ListNode(3); h.next.next.next = new ListNode(4);
        ListNode res = swapPairs(h);
        while (res != null) { System.out.print(res.val + " "); res = res.next; } // 2 1 4 3
    }
}
