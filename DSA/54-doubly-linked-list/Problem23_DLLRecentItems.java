import java.util.*;

public class Problem23_DLLRecentItems {
    static class Node{String item;Node prev,next;Node(String s){item=s;}}
    Node head=new Node(""),tail=new Node(""); int size,cap;
    Map<String,Node> map=new HashMap<>();
    
    Problem23_DLLRecentItems(int c){cap=c;head.next=tail;tail.prev=head;}
    
    void add(String item){
        if(map.containsKey(item)){Node n=map.get(item);n.prev.next=n.next;n.next.prev=n.prev;addFront(n);}
        else{Node n=new Node(item);map.put(item,n);addFront(n);size++;if(size>cap){Node rm=tail.prev;rm.prev.next=tail;tail.prev=rm.prev;map.remove(rm.item);size--;}}
    }
    
    void addFront(Node n){n.next=head.next;n.prev=head;head.next.prev=n;head.next=n;}
    
    List<String> getRecent(){List<String> r=new ArrayList<>();Node c=head.next;while(c!=tail){r.add(c.item);c=c.next;}return r;}
    
    public static void main(String[] args) {
        Problem23_DLLRecentItems ri=new Problem23_DLLRecentItems(3);
        ri.add("a");ri.add("b");ri.add("c");ri.add("b");ri.add("d");
        System.out.println(ri.getRecent()); // [d, b, c]
    }
}
