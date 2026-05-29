import java.util.*;

public class Problem47_DLLWithHashMapO1Search {
    static class Node{int key,val;Node prev,next;Node(int k,int v){key=k;val=v;}}
    Node head=new Node(0,0),tail=new Node(0,0);
    Map<Integer,Node>map=new HashMap<>();
    
    Problem47_DLLWithHashMapO1Search(){head.next=tail;tail.prev=head;}
    
    void put(int key,int val){
        if(map.containsKey(key)){map.get(key).val=val;return;}
        Node n=new Node(key,val);map.put(key,n);
        n.prev=tail.prev;n.next=tail;tail.prev.next=n;tail.prev=n;
    }
    int get(int key){return map.containsKey(key)?map.get(key).val:-1;}
    void delete(int key){if(!map.containsKey(key))return;Node n=map.remove(key);n.prev.next=n.next;n.next.prev=n.prev;}
    
    public static void main(String[] args) {
        Problem47_DLLWithHashMapO1Search ds=new Problem47_DLLWithHashMapO1Search();
        ds.put(1,10);ds.put(2,20);ds.put(3,30);
        System.out.println(ds.get(2)); // 20
        ds.delete(2);
        System.out.println(ds.get(2)); // -1
    }
}
