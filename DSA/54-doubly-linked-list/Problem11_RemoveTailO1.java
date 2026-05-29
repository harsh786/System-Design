public class Problem11_RemoveTailO1 {
    static class Node { int val; Node prev, next; Node(int v){val=v;} }
    Node head=new Node(0), tail=new Node(0);
    Problem11_RemoveTailO1(){head.next=tail;tail.prev=head;}
    
    void add(int val) { Node n=new Node(val); n.next=tail;n.prev=tail.prev;tail.prev.next=n;tail.prev=n; }
    int removeTail() { Node n=tail.prev; if(n==head)return -1; n.prev.next=tail;tail.prev=n.prev; return n.val; }
    
    public static void main(String[] args) {
        Problem11_RemoveTailO1 dll=new Problem11_RemoveTailO1();
        dll.add(1);dll.add(2);dll.add(3);
        System.out.println(dll.removeTail()); // 3
        System.out.println(dll.removeTail()); // 2
    }
}
