public class Problem31_DLLNodeRemovalO1 {
    static class Node{int val;Node prev,next;Node(int v){val=v;}}
    
    static void removeO1(Node node) { // O(1) given reference
        node.prev.next = node.next; node.next.prev = node.prev;
    }
    
    static void print(Node head){Node c=head;while(c!=null){System.out.print(c.val+" ");c=c.next;}System.out.println();}
    
    public static void main(String[] args) {
        Node sentinel=new Node(0),a=new Node(1),b=new Node(2),c=new Node(3),end=new Node(0);
        sentinel.next=a;a.prev=sentinel;a.next=b;b.prev=a;b.next=c;c.prev=b;c.next=end;end.prev=c;
        removeO1(b);
        print(sentinel.next); // 1 3 0
    }
}
