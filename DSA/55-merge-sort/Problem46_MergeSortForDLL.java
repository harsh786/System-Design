public class Problem46_MergeSortForDLL {
    static class Node{int val;Node prev,next;Node(int v){val=v;}}
    
    static Node sort(Node head) {
        if (head == null || head.next == null) return head;
        Node mid = getMid(head); Node second = mid.next; mid.next = null; if(second!=null)second.prev=null;
        return merge(sort(head), sort(second));
    }
    
    static Node getMid(Node h){Node s=h,f=h;while(f.next!=null&&f.next.next!=null){s=s.next;f=f.next.next;}return s;}
    
    static Node merge(Node a, Node b) {
        Node d=new Node(0),c=d;
        while(a!=null&&b!=null){if(a.val<=b.val){c.next=a;a.prev=c;a=a.next;}else{c.next=b;b.prev=c;b=b.next;}c=c.next;}
        Node rem=a!=null?a:b;if(rem!=null){c.next=rem;rem.prev=c;}
        Node res=d.next;if(res!=null)res.prev=null;return res;
    }
    
    static void print(Node h){while(h!=null){System.out.print(h.val+" ");h=h.next;}System.out.println();}
    
    public static void main(String[] args) {
        Node a=new Node(5),b=new Node(3),c=new Node(8),d=new Node(1);
        a.next=b;b.prev=a;b.next=c;c.prev=b;c.next=d;d.prev=c;
        print(sort(a)); // 1 3 5 8
    }
}
