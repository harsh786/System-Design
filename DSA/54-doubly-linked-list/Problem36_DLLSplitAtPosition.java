public class Problem36_DLLSplitAtPosition {
    static class Node{int val;Node prev,next;Node(int v){val=v;}}
    
    static Node[] split(Node head, int pos) {
        Node cur=head;for(int i=0;i<pos-1&&cur!=null;i++)cur=cur.next;
        if(cur==null||cur.next==null)return new Node[]{head,null};
        Node second=cur.next;cur.next=null;second.prev=null;
        return new Node[]{head,second};
    }
    
    static void print(Node h){while(h!=null){System.out.print(h.val+" ");h=h.next;}System.out.println();}
    
    public static void main(String[] args) {
        Node a=new Node(1),b=new Node(2),c=new Node(3),d=new Node(4);
        a.next=b;b.prev=a;b.next=c;c.prev=b;c.next=d;d.prev=c;
        Node[] parts=split(a,2);
        print(parts[0]); // 1 2
        print(parts[1]); // 3 4
    }
}
