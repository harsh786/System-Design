public class Problem46_DLLConsistencyCheck {
    static class Node{int val;Node prev,next;Node(int v){val=v;}}
    
    static boolean isConsistent(Node head) {
        if(head==null)return true;
        Node cur=head;
        if(cur.prev!=null)return false; // head should have no prev
        while(cur.next!=null){
            if(cur.next.prev!=cur)return false;
            cur=cur.next;
        }
        return true;
    }
    
    public static void main(String[] args) {
        Node a=new Node(1),b=new Node(2),c=new Node(3);
        a.next=b;b.prev=a;b.next=c;c.prev=b;
        System.out.println("Consistent: "+isConsistent(a)); // true
        c.prev=a; // corrupt
        System.out.println("After corruption: "+isConsistent(a)); // false
    }
}
