public class Problem12_SpliceListSegment {
    static class Node { int val; Node prev, next; Node(int v){val=v;} }
    
    // Move segment [start..end] after target
    static void splice(Node start, Node end, Node target) {
        // Detach segment
        start.prev.next = end.next;
        if (end.next != null) end.next.prev = start.prev;
        // Insert after target
        Node afterTarget = target.next;
        target.next = start; start.prev = target;
        end.next = afterTarget; if (afterTarget != null) afterTarget.prev = end;
    }
    
    static void print(Node h){while(h!=null){System.out.print(h.val+" ");h=h.next;}System.out.println();}
    
    public static void main(String[] args) {
        Node a=new Node(1),b=new Node(2),c=new Node(3),d=new Node(4),e=new Node(5);
        a.next=b;b.prev=a;b.next=c;c.prev=b;c.next=d;d.prev=c;d.next=e;e.prev=d;
        splice(b, c, d); // move [2,3] after 4: 1 4 2 3 5
        print(a);
    }
}
