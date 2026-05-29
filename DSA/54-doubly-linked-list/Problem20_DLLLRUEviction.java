import java.util.*;

public class Problem20_DLLLRUEviction {
    static class Node{String key;Node prev,next;Node(String k){key=k;}}
    Node head=new Node(""),tail=new Node("");
    Map<String,Node> map=new HashMap<>(); int cap;
    
    Problem20_DLLLRUEviction(int c){cap=c;head.next=tail;tail.prev=head;}
    
    void access(String key){
        if(map.containsKey(key)){Node n=map.get(key);remove(n);addFront(n);}
        else{Node n=new Node(key);map.put(key,n);addFront(n);if(map.size()>cap)evict();}
    }
    String evict(){Node n=tail.prev;remove(n);map.remove(n.key);return n.key;}
    void remove(Node n){n.prev.next=n.next;n.next.prev=n.prev;}
    void addFront(Node n){n.next=head.next;n.prev=head;head.next.prev=n;head.next=n;}
    
    public static void main(String[] args) {
        Problem20_DLLLRUEviction c=new Problem20_DLLLRUEviction(3);
        c.access("a");c.access("b");c.access("c");c.access("a");c.access("d");
        System.out.println("Evicted: b (LRU). Current head: "+c.head.next.key);
    }
}
