import java.util.*;

public class Problem21_DLLLFUFrequencyBuckets {
    // Simplified LFU with frequency buckets as DLL
    static class Node{String key;int freq;Node prev,next;Node(String k){key=k;freq=1;}}
    static class Bucket{int freq;Set<String> keys=new HashSet<>();Bucket prev,next;Bucket(int f){freq=f;}}
    
    Map<String,Node> cache=new HashMap<>();
    Bucket head=new Bucket(0),tail=new Bucket(Integer.MAX_VALUE);
    int cap;
    
    Problem21_DLLLFUFrequencyBuckets(int c){cap=c;head.next=tail;tail.prev=head;}
    
    void access(String key){
        if(cache.containsKey(key)){cache.get(key).freq++;System.out.println("Access "+key+" freq="+cache.get(key).freq);}
        else{if(cache.size()>=cap)System.out.println("Evict LFU");Node n=new Node(key);cache.put(key,n);System.out.println("Add "+key);}
    }
    
    public static void main(String[] args) {
        Problem21_DLLLFUFrequencyBuckets lfu=new Problem21_DLLLFUFrequencyBuckets(3);
        lfu.access("a");lfu.access("b");lfu.access("a");lfu.access("c");lfu.access("d");
    }
}
