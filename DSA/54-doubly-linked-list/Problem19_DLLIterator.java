import java.util.*;

public class Problem19_DLLIterator {
    static class Node{int val;Node prev,next;Node(int v){val=v;}}
    
    static class DLLIterator implements Iterator<Integer> {
        Node cur;
        DLLIterator(Node head){cur=head;}
        public boolean hasNext(){return cur!=null;}
        public Integer next(){int v=cur.val;cur=cur.next;return v;}
        public void previous(){if(cur!=null&&cur.prev!=null)cur=cur.prev;}
    }
    
    public static void main(String[] args) {
        Node a=new Node(1),b=new Node(2),c=new Node(3);
        a.next=b;b.prev=a;b.next=c;c.prev=b;
        DLLIterator it=new DLLIterator(a);
        while(it.hasNext()) System.out.print(it.next()+" ");
        System.out.println();
    }
}
