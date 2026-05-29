public class Problem33_DLLSentinelNodesPattern {
    static class Node{int val;Node prev,next;Node(int v){val=v;}}
    Node head,tail;int size;
    
    Problem33_DLLSentinelNodesPattern(){head=new Node(Integer.MIN_VALUE);tail=new Node(Integer.MAX_VALUE);head.next=tail;tail.prev=head;}
    
    void add(int val){Node n=new Node(val);n.prev=tail.prev;n.next=tail;tail.prev.next=n;tail.prev=n;size++;}
    void removeFirst(){if(size>0){Node n=head.next;head.next=n.next;n.next.prev=head;size--;}}
    boolean isEmpty(){return size==0;}
    
    void print(){Node c=head.next;while(c!=tail){System.out.print(c.val+" ");c=c.next;}System.out.println();}
    
    public static void main(String[] args) {
        Problem33_DLLSentinelNodesPattern dll=new Problem33_DLLSentinelNodesPattern();
        dll.add(10);dll.add(20);dll.add(30);dll.removeFirst();
        dll.print(); // 20 30
    }
}
