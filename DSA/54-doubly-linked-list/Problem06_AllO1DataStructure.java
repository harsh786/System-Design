import java.util.*;

public class Problem06_AllO1DataStructure {
    static class Bucket { int count; Set<String> keys = new HashSet<>(); Bucket prev, next;
        Bucket(int c) { count=c; } }
    
    Map<String, Integer> keyCount = new HashMap<>();
    Map<Integer, Bucket> countBucket = new HashMap<>();
    Bucket head = new Bucket(0), tail = new Bucket(Integer.MAX_VALUE);
    
    Problem06_AllO1DataStructure() { head.next=tail; tail.prev=head; }
    
    void inc(String key) {
        int c = keyCount.getOrDefault(key, 0);
        keyCount.put(key, c + 1);
        if (c > 0) countBucket.get(c).keys.remove(key);
        Bucket after = c > 0 ? countBucket.get(c) : head;
        if (!countBucket.containsKey(c+1)) { Bucket b=new Bucket(c+1); insertAfter(after,b); countBucket.put(c+1,b); }
        countBucket.get(c+1).keys.add(key);
        if (c > 0 && countBucket.get(c).keys.isEmpty()) removeBucket(countBucket.remove(c));
    }
    
    void dec(String key) {
        int c = keyCount.get(key);
        if (c == 1) keyCount.remove(key); else keyCount.put(key, c-1);
        countBucket.get(c).keys.remove(key);
        if (c > 1) {
            Bucket before = countBucket.get(c);
            if (!countBucket.containsKey(c-1)) { Bucket b=new Bucket(c-1); insertBefore(before,b); countBucket.put(c-1,b); }
            countBucket.get(c-1).keys.add(key);
        }
        if (countBucket.get(c).keys.isEmpty()) removeBucket(countBucket.remove(c));
    }
    
    String getMaxKey() { return tail.prev==head ? "" : tail.prev.keys.iterator().next(); }
    String getMinKey() { return head.next==tail ? "" : head.next.keys.iterator().next(); }
    
    void insertAfter(Bucket node, Bucket b) { b.next=node.next; b.prev=node; node.next.prev=b; node.next=b; }
    void insertBefore(Bucket node, Bucket b) { insertAfter(node.prev, b); }
    void removeBucket(Bucket b) { b.prev.next=b.next; b.next.prev=b.prev; }
    
    public static void main(String[] args) {
        Problem06_AllO1DataStructure ds = new Problem06_AllO1DataStructure();
        ds.inc("a"); ds.inc("b"); ds.inc("b");
        System.out.println("Max: " + ds.getMaxKey()); // b
        System.out.println("Min: " + ds.getMinKey()); // a
    }
}
