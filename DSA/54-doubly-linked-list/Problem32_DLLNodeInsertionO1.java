public class Problem32_DLLNodeInsertionO1 {
    static class Node{int val;Node prev,next;Node(int v){val=v;}}
    
    static void insertAfter(Node target, Node newNode) {
        newNode.next=target.next;newNode.prev=target;
        if(target.next!=null)target.next.prev=newNode;
        target.next=newNode;
    }
    
    static void insertBefore(Node target, Node newNode) {
        newNode.prev=target.prev;newNode.next=target;
        if(target.prev!=null)target.prev.next=newNode;
        target.prev=newNode;
    }
    
    static void print(Node h){while(h!=null){System.out.print(h.val+" ");h=h.next;}System.out.println();}
    
    public static void main(String[] args) {
        Node a=new Node(1),b=new Node(3);a.next=b;b.prev=a;
        insertAfter(a,new Node(2));
        print(a); // 1 2 3
    }
}
