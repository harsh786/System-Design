public class Problem39_DLLSortMergeSort {
    static class Node{int val;Node prev,next;Node(int v){val=v;}}
    
    static Node sort(Node head) {
        if(head==null||head.next==null)return head;
        Node mid=getMid(head);Node second=mid.next;mid.next=null;if(second!=null)second.prev=null;
        return merge(sort(head),sort(second));
    }
    
    static Node getMid(Node head){Node slow=head,fast=head;while(fast.next!=null&&fast.next.next!=null){slow=slow.next;fast=fast.next.next;}return slow;}
    
    static Node merge(Node a,Node b){
        Node dummy=new Node(0),cur=dummy;
        while(a!=null&&b!=null){if(a.val<=b.val){cur.next=a;a.prev=cur;a=a.next;}else{cur.next=b;b.prev=cur;b=b.next;}cur=cur.next;}
        Node rem=a!=null?a:b;if(rem!=null){cur.next=rem;rem.prev=cur;}
        Node res=dummy.next;if(res!=null)res.prev=null;return res;
    }
    
    static void print(Node h){while(h!=null){System.out.print(h.val+" ");h=h.next;}System.out.println();}
    
    public static void main(String[] args) {
        Node a=new Node(4),b=new Node(2),c=new Node(5),d=new Node(1),e=new Node(3);
        a.next=b;b.prev=a;b.next=c;c.prev=b;c.next=d;d.prev=c;d.next=e;e.prev=d;
        print(sort(a)); // 1 2 3 4 5
    }
}
