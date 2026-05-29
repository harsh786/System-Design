import java.util.*;

public class Problem26_DLLPageCache {
    static class Page{int id;byte[] data;Page prev,next;Page(int i){id=i;data=new byte[4096];}}
    Page head=new Page(-1),tail=new Page(-1);Map<Integer,Page>map=new HashMap<>();int cap;
    Problem26_DLLPageCache(int c){cap=c;head.next=tail;tail.prev=head;}
    
    byte[] getPage(int id){
        if(map.containsKey(id)){Page p=map.get(id);remove(p);addFront(p);return p.data;}
        Page p=new Page(id);// simulate disk read
        map.put(id,p);addFront(p);
        if(map.size()>cap){Page evict=tail.prev;remove(evict);map.remove(evict.id);}
        return p.data;
    }
    void remove(Page p){p.prev.next=p.next;p.next.prev=p.prev;}
    void addFront(Page p){p.next=head.next;p.prev=head;head.next.prev=p;head.next=p;}
    
    public static void main(String[] args) {
        Problem26_DLLPageCache cache=new Problem26_DLLPageCache(3);
        cache.getPage(1);cache.getPage(2);cache.getPage(3);cache.getPage(1);cache.getPage(4);
        System.out.println("Cache contains: "+cache.map.keySet()); // [1,3,4] or [4,1,3]
    }
}
