public class Problem38_DLLSwapPairs {
    static class Node{int val;Node prev,next;Node(int v){val=v;}}
    
    static Node swapPairs(Node head) {
        Node dummy=new Node(0);dummy.next=head;if(head!=null)head.prev=dummy;
        Node cur=dummy;
        while(cur.next!=null&&cur.next.next!=null){
            Node a=cur.next,b=a.next;
            a.next=b.next;if(b.next!=null)b.next.prev=a;
            cur.next=b;b.prev=cur;b.next=a;a.prev=b;
            cur=a;
        }
        Node res=dummy.next;if(res!=null)res.prev=null;
        return res;
    }
    
    static void print(Node h){while(h!=null){System.out.print(h.val+" ");h=h.next;}System.out.println();}
    
    public static void main(String[] args) {
        Node a=new Node(1),b=new Node(2),c=new Node(3),d=new Node(4);
        a.next=b;b.prev=a;b.next=c;c.prev=b;c.next=d;d.prev=c;
        print(swapPairs(a)); // 2 1 4 3
    }
}
