import java.util.*;

public class Problem02_LFUCache {
    static class Node { int key, val, freq; Node prev, next;
        Node(int k, int v) { key=k; val=v; freq=1; } }
    static class DLL { Node head=new Node(0,0), tail=new Node(0,0); int size;
        DLL() { head.next=tail; tail.prev=head; }
        void addFront(Node n) { n.next=head.next; n.prev=head; head.next.prev=n; head.next=n; size++; }
        void remove(Node n) { n.prev.next=n.next; n.next.prev=n.prev; size--; }
        Node removeLast() { Node n=tail.prev; remove(n); return n; } }
    
    int cap, minFreq;
    Map<Integer,Node> cache = new HashMap<>();
    Map<Integer,DLL> freqMap = new HashMap<>();
    
    Problem02_LFUCache(int c) { cap=c; }
    
    int get(int key) {
        if (!cache.containsKey(key)) return -1;
        Node n = cache.get(key); updateFreq(n); return n.val;
    }
    
    void put(int key, int val) {
        if (cap == 0) return;
        if (cache.containsKey(key)) { Node n=cache.get(key); n.val=val; updateFreq(n); return; }
        if (cache.size() == cap) { DLL dll=freqMap.get(minFreq); Node rm=dll.removeLast(); cache.remove(rm.key); }
        Node n = new Node(key, val); cache.put(key, n); minFreq = 1;
        freqMap.computeIfAbsent(1, k->new DLL()).addFront(n);
    }
    
    void updateFreq(Node n) {
        DLL old = freqMap.get(n.freq); old.remove(n);
        if (n.freq == minFreq && old.size == 0) minFreq++;
        n.freq++;
        freqMap.computeIfAbsent(n.freq, k->new DLL()).addFront(n);
    }
    
    public static void main(String[] args) {
        Problem02_LFUCache c = new Problem02_LFUCache(2);
        c.put(1,1); c.put(2,2); System.out.println(c.get(1)); // 1
        c.put(3,3); System.out.println(c.get(2)); // -1
        System.out.println(c.get(3)); // 3
    }
}
