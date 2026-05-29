import java.util.*;

public class Problem50_DLLForEventOrdering {
    static class Event{long timestamp;String name;Event prev,next;Event(long t,String n){timestamp=t;name=n;}}
    Event head=new Event(Long.MIN_VALUE,""),tail=new Event(Long.MAX_VALUE,"");
    
    Problem50_DLLForEventOrdering(){head.next=tail;tail.prev=head;}
    
    void addEvent(long ts,String name){
        Event e=new Event(ts,name);
        // Insert in sorted order
        Event cur=tail.prev;
        while(cur!=head&&cur.timestamp>ts)cur=cur.prev;
        e.next=cur.next;e.prev=cur;cur.next.prev=e;cur.next=e;
    }
    
    List<String> getEventsInRange(long start,long end){
        List<String> r=new ArrayList<>();
        Event cur=head.next;
        while(cur!=tail&&cur.timestamp<start)cur=cur.next;
        while(cur!=tail&&cur.timestamp<=end){r.add(cur.name);cur=cur.next;}
        return r;
    }
    
    public static void main(String[] args) {
        Problem50_DLLForEventOrdering eo=new Problem50_DLLForEventOrdering();
        eo.addEvent(100,"login");eo.addEvent(50,"boot");eo.addEvent(200,"query");eo.addEvent(150,"auth");
        System.out.println(eo.getEventsInRange(80,160)); // [login, auth]
    }
}
