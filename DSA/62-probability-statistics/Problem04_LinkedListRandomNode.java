import java.util.*;

public class Problem04_LinkedListRandomNode {
    static class ListNode { int val; ListNode next; ListNode(int v) { val = v; } }
    private ListNode head;
    private Random rand = new Random();

    public Problem04_LinkedListRandomNode(ListNode head) { this.head = head; }

    public int getRandom() {
        int result = head.val;
        ListNode cur = head.next;
        int i = 2;
        while (cur != null) {
            if (rand.nextInt(i) == 0) result = cur.val;
            cur = cur.next; i++;
        }
        return result;
    }

    public static void main(String[] args) {
        ListNode head = new ListNode(1); head.next = new ListNode(2); head.next.next = new ListNode(3);
        Problem04_LinkedListRandomNode sol = new Problem04_LinkedListRandomNode(head);
        int[] freq = new int[4];
        for (int i = 0; i < 9000; i++) freq[sol.getRandom()]++;
        System.out.println(Arrays.toString(freq));
    }
}
