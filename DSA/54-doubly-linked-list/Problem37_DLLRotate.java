public class Problem37_DLLRotate {
    static class Node{int val;Node prev,next;Node(int v){val=v;}}
    
    static Node rotate(Node head, int k) {
        if(head==null)return null;
        int len=1;Node tail=head;while(tail.next!=null){tail=tail.next;len++;}
        k=k%len;if(k==0)return head;
        // Find new tail at position len-k-1
        Node newTail=head;for(int i=0;i<len-k-1;i++)newTail=newTail.next;
        Node newHead=newTail.next;
        newTail.next=null;newHead.prev=null;
        tail.next=head;head.prev=tail;
        return newHead;
    }
    
    static void print(Node h){while(h!=null){System.out.print(h.val+" ");h=h.next;}System.out.println();}
    
    public static void main(String[] args) {
        Node a=new Node(1),b=new Node(2),c=new Node(3),d=new Node(4),e=new Node(5);
        a.next=b;b.prev=a;b.next=c;c.prev=b;c.next=d;d.prev=c;d.next=e;e.prev=d;
        print(rotate(a,2)); // 4 5 1 2 3
    }
}
