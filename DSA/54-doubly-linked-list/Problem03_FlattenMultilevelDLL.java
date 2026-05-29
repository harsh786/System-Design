public class Problem03_FlattenMultilevelDLL {
    static class Node { int val; Node prev, next, child;
        Node(int v) { val=v; } }
    
    static Node flatten(Node head) {
        Node cur = head;
        while (cur != null) {
            if (cur.child != null) {
                Node child = cur.child, next = cur.next;
                Node childTail = child;
                while (childTail.next != null) childTail = childTail.next;
                cur.next = child; child.prev = cur; cur.child = null;
                childTail.next = next; if (next != null) next.prev = childTail;
            }
            cur = cur.next;
        }
        return head;
    }
    
    public static void main(String[] args) {
        Node n1=new Node(1), n2=new Node(2), n3=new Node(3), n4=new Node(4);
        n1.next=n2; n2.prev=n1; n2.next=n3; n3.prev=n2;
        n2.child=n4;
        Node res = flatten(n1);
        while (res != null) { System.out.print(res.val + " "); res = res.next; }
        System.out.println(); // 1 2 4 3
    }
}
