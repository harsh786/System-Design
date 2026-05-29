import java.util.*;

public class Problem08_LinkedListRandomNode {
    // Reservoir sampling on linked list
    static class ListNode {
        int val; ListNode next;
        ListNode(int v) { val = v; }
    }

    ListNode head;
    Random rand;

    public Problem08_LinkedListRandomNode(ListNode head) {
        this.head = head;
        this.rand = new Random();
    }

    public int getRandom() {
        ListNode cur = head;
        int result = cur.val, count = 1;
        while (cur != null) {
            if (rand.nextInt(count) == 0) result = cur.val;
            count++;
            cur = cur.next;
        }
        return result;
    }

    public static void main(String[] args) {
        ListNode head = new ListNode(1);
        head.next = new ListNode(2);
        head.next.next = new ListNode(3);
        Problem08_LinkedListRandomNode sol = new Problem08_LinkedListRandomNode(head);
        for (int i = 0; i < 10; i++) System.out.print(sol.getRandom() + " ");
        System.out.println();
    }
}
