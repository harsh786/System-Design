import java.util.*;

public class Problem08_CopyListRandomPointer {
    static class Node { int val; Node next, prev, random; Node(int v){val=v;} }
    
    static Node copyRandomList(Node head) {
        if (head == null) return null;
        Map<Node, Node> map = new HashMap<>();
        Node cur = head;
        while (cur != null) { map.put(cur, new Node(cur.val)); cur = cur.next; }
        cur = head;
        while (cur != null) {
            map.get(cur).next = map.get(cur.next);
            if (cur.next != null) map.get(cur.next).prev = map.get(cur);
            map.get(cur).random = map.get(cur.random);
            cur = cur.next;
        }
        return map.get(head);
    }
    
    public static void main(String[] args) {
        Node a=new Node(1), b=new Node(2), c=new Node(3);
        a.next=b; b.prev=a; b.next=c; c.prev=b;
        a.random=c; b.random=a; c.random=b;
        Node copy = copyRandomList(a);
        Node cur = copy;
        while (cur != null) { System.out.println(cur.val + " random=" + (cur.random!=null?cur.random.val:-1)); cur = cur.next; }
    }
}
