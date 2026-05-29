import java.util.*;

public class Problem30_DLLHashMapIntegration {
    // LinkedHashMap equivalent: HashMap + DLL for order
    static class Entry{String key,val;Entry prev,next;Entry(String k,String v){key=k;val=v;}}
    Entry head=new Entry("",""),tail=new Entry("","");
    Map<String,Entry> map=new HashMap<>();
    
    Problem30_DLLHashMapIntegration(){head.next=tail;tail.prev=head;}
    
    void put(String k,String v){
        if(map.containsKey(k)){map.get(k).val=v;return;}
        Entry e=new Entry(k,v);e.prev=tail.prev;e.next=tail;tail.prev.next=e;tail.prev=e;map.put(k,e);
    }
    String get(String k){return map.containsKey(k)?map.get(k).val:null;}
    void remove(String k){if(!map.containsKey(k))return;Entry e=map.remove(k);e.prev.next=e.next;e.next.prev=e.prev;}
    
    void printOrder(){Entry c=head.next;while(c!=tail){System.out.print(c.key+"="+c.val+" ");c=c.next;}System.out.println();}
    
    public static void main(String[] args) {
        Problem30_DLLHashMapIntegration m=new Problem30_DLLHashMapIntegration();
        m.put("x","1");m.put("y","2");m.put("z","3");
        m.remove("y");
        m.printOrder(); // x=1 z=3
    }
}
