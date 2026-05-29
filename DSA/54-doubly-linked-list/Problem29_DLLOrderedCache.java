import java.util.*;

public class Problem29_DLLOrderedCache {
    // Cache that maintains insertion order with O(1) access
    static class Node{String key,val;Node prev,next;Node(String k,String v){key=k;val=v;}}
    Node head=new Node("",""),tail=new Node("","");
    Map<String,Node> map=new HashMap<>();
    
    Problem29_DLLOrderedCache(){head.next=tail;tail.prev=head;}
    
    void put(String key,String val){
        if(map.containsKey(key)){map.get(key).val=val;return;}
        Node n=new Node(key,val);n.prev=tail.prev;n.next=tail;tail.prev.next=n;tail.prev=n;map.put(key,n);
    }
    String get(String key){return map.containsKey(key)?map.get(key).val:null;}
    List<String> orderedKeys(){List<String> r=new ArrayList<>();Node c=head.next;while(c!=tail){r.add(c.key);c=c.next;}return r;}
    
    public static void main(String[] args) {
        Problem29_DLLOrderedCache c=new Problem29_DLLOrderedCache();
        c.put("b","2");c.put("a","1");c.put("c","3");
        System.out.println(c.orderedKeys()); // [b, a, c]
        System.out.println(c.get("a")); // 1
    }
}
