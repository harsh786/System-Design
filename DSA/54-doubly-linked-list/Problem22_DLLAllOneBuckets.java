import java.util.*;

public class Problem22_DLLAllOneBuckets {
    // AllO(1) with DLL of count buckets - same as Problem06 simplified demo
    static class Bucket{int count;Set<String> keys=new HashSet<>();Bucket prev,next;Bucket(int c){count=c;}}
    Bucket head=new Bucket(0),tail=new Bucket(Integer.MAX_VALUE);
    Map<String,Integer> keyCount=new HashMap<>();
    Map<Integer,Bucket> countMap=new HashMap<>();
    
    Problem22_DLLAllOneBuckets(){head.next=tail;tail.prev=head;}
    
    void inc(String key){
        int c=keyCount.getOrDefault(key,0); keyCount.put(key,c+1);
        if(c>0&&countMap.containsKey(c))countMap.get(c).keys.remove(key);
        countMap.computeIfAbsent(c+1,k->{Bucket b=new Bucket(c+1);Bucket after=countMap.containsKey(c)?countMap.get(c):head;b.next=after.next;b.prev=after;after.next.prev=b;after.next=b;return b;}).keys.add(key);
        if(c>0&&countMap.containsKey(c)&&countMap.get(c).keys.isEmpty()){Bucket b=countMap.remove(c);b.prev.next=b.next;b.next.prev=b.prev;}
    }
    
    String getMax(){return tail.prev==head?"":tail.prev.keys.iterator().next();}
    String getMin(){return head.next==tail?"":head.next.keys.iterator().next();}
    
    public static void main(String[] args) {
        Problem22_DLLAllOneBuckets ds=new Problem22_DLLAllOneBuckets();
        ds.inc("a");ds.inc("b");ds.inc("b");ds.inc("c");ds.inc("c");ds.inc("c");
        System.out.println("Max: "+ds.getMax()+" Min: "+ds.getMin()); // c, a
    }
}
