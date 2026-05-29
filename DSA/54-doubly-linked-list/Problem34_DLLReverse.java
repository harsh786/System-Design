public class Problem34_DLLReverse {
    static class Node{int val;Node prev,next;Node(int v){val=v;}}
    
    static Node reverse(Node head) {
        Node cur=head;
        while(cur!=null){Node tmp=cur.prev;cur.prev=cur.next;cur.next=tmp;
            if(cur.prev==null) return cur; cur=cur.prev;}
        return head;
    }
    
    static void print(Node h){while(h!=null){System.out.print(h.val+" ");h=h.next;}System.out.println();}
    
    public static void main(String[] args) {
        Node a=new Node(1),b=new Node(2),c=new Node(3),d=new Node(4);
        a.next=b;b.prev=a;b.next=c;c.prev=b;c.next=d;d.prev=c;
        print(reverse(a)); // 4 3 2 1
    }
}
