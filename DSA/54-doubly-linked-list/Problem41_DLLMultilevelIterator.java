import java.util.*;

public class Problem41_DLLMultilevelIterator {
    static class Node{int val;Node prev,next,child;Node(int v){val=v;}}
    
    static List<Integer> iterate(Node head) {
        List<Integer> result=new ArrayList<>();
        Deque<Node> stack=new ArrayDeque<>();
        Node cur=head;
        while(cur!=null||!stack.isEmpty()){
            if(cur==null){cur=stack.pop();continue;}
            result.add(cur.val);
            if(cur.next!=null)stack.push(cur.next);
            cur=cur.child!=null?cur.child:(!stack.isEmpty()?stack.pop():null);
        }
        return result;
    }
    
    public static void main(String[] args) {
        Node a=new Node(1),b=new Node(2),c=new Node(3),d=new Node(4);
        a.next=b;b.prev=a;a.child=c;c.child=d;
        System.out.println(iterate(a)); // [1, 3, 4, 2]
    }
}
