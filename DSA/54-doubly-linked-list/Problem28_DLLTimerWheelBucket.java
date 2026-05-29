import java.util.*;

public class Problem28_DLLTimerWheelBucket {
    static class Timer{int id;long expiry;Timer prev,next;Timer(int i,long e){id=i;expiry=e;}}
    static class Bucket{Timer head=new Timer(-1,0),tail=new Timer(-1,0);
        Bucket(){head.next=tail;tail.prev=head;}
        void add(Timer t){t.next=tail;t.prev=tail.prev;tail.prev.next=t;tail.prev=t;}
        void remove(Timer t){t.prev.next=t.next;t.next.prev=t.prev;}
        List<Integer> expire(){List<Integer> r=new ArrayList<>();Timer c=head.next;while(c!=tail){r.add(c.id);c=c.next;}head.next=tail;tail.prev=head;return r;}
    }
    
    Bucket[] wheel;int size;
    Problem28_DLLTimerWheelBucket(int slots){size=slots;wheel=new Bucket[slots];for(int i=0;i<slots;i++)wheel[i]=new Bucket();}
    
    void addTimer(int id,int ticks){wheel[ticks%size].add(new Timer(id,ticks));}
    List<Integer> tick(int slot){return wheel[slot%size].expire();}
    
    public static void main(String[] args) {
        Problem28_DLLTimerWheelBucket tw=new Problem28_DLLTimerWheelBucket(8);
        tw.addTimer(1,3);tw.addTimer(2,3);tw.addTimer(3,5);
        System.out.println("Tick 3: "+tw.tick(3)); // [1,2]
        System.out.println("Tick 5: "+tw.tick(5)); // [3]
    }
}
