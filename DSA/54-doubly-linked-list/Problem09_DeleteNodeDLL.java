public class Problem09_DeleteNodeDLL {
    static class Node { int val; Node prev, next; Node(int v){val=v;} }
    
    static Node delete(Node head, Node target) {
        if (target == head) head = head.next;
        if (target.prev != null) target.prev.next = target.next;
        if (target.next != null) target.next.prev = target.prev;
        return head;
    }
    
    static void print(Node head) { while(head!=null){System.out.print(head.val+" ");head=head.next;} System.out.println(); }
    
    public static void main(String[] args) {
        Node a=new Node(1),b=new Node(2),c=new Node(3);
        a.next=b;b.prev=a;b.next=c;c.prev=b;
        print(delete(a, b)); // 1 3
    }
}
