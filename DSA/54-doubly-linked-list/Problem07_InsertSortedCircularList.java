public class Problem07_InsertSortedCircularList {
    static class Node { int val; Node next, prev; Node(int v){val=v;} }
    
    static Node insert(Node head, int val) {
        Node n = new Node(val); n.next = n; n.prev = n;
        if (head == null) return n;
        Node cur = head;
        do {
            if ((cur.val <= val && val <= cur.next.val) ||
                (cur.val > cur.next.val && (val >= cur.val || val <= cur.next.val))) {
                n.next = cur.next; n.prev = cur; cur.next.prev = n; cur.next = n;
                return head;
            }
            cur = cur.next;
        } while (cur != head);
        n.next = cur.next; n.prev = cur; cur.next.prev = n; cur.next = n;
        return head;
    }
    
    public static void main(String[] args) {
        Node head = null;
        for (int v : new int[]{3, 1, 4, 1, 5}) head = insert(head, v);
        Node cur = head; do { System.out.print(cur.val + " "); cur = cur.next; } while (cur != head);
        System.out.println();
    }
}
