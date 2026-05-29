public class Problem35_DLLMergeTwoLists {
    static class Node{int val;Node prev,next;Node(int v){val=v;}}
    
    static Node merge(Node l1, Node l2) {
        Node dummy=new Node(0),cur=dummy;
        while(l1!=null&&l2!=null){
            if(l1.val<=l2.val){cur.next=l1;l1.prev=cur;l1=l1.next;}
            else{cur.next=l2;l2.prev=cur;l2=l2.next;}
            cur=cur.next;
        }
        Node rem=l1!=null?l1:l2;
        if(rem!=null){cur.next=rem;rem.prev=cur;}
        Node head=dummy.next;if(head!=null)head.prev=null;
        return head;
    }
    
    static void print(Node h){while(h!=null){System.out.print(h.val+" ");h=h.next;}System.out.println();}
    
    public static void main(String[] args) {
        Node a=new Node(1),b=new Node(3),c=new Node(5);a.next=b;b.prev=a;b.next=c;c.prev=b;
        Node d=new Node(2),e=new Node(4);d.next=e;e.prev=d;
        print(merge(a,d)); // 1 2 3 4 5
    }
}
