public class Problem10_MoveNodeToFront {
    static class Node { int val; Node prev, next; Node(int v){val=v;} }
    
    static Node moveToFront(Node head, Node target) {
        if (target == head) return head;
        if (target.prev != null) target.prev.next = target.next;
        if (target.next != null) target.next.prev = target.prev;
        target.prev = null; target.next = head; head.prev = target;
        return target;
    }
    
    static void print(Node h) { while(h!=null){System.out.print(h.val+" ");h=h.next;} System.out.println(); }
    
    public static void main(String[] args) {
        Node a=new Node(1),b=new Node(2),c=new Node(3);
        a.next=b;b.prev=a;b.next=c;c.prev=b;
        print(moveToFront(a, c)); // 3 1 2
    }
}
