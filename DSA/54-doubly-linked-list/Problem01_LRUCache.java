import java.util.*;

public class Problem01_LRUCache {
    static class Node { int key, val; Node prev, next;
        Node(int k, int v) { key=k; val=v; } }
    
    int cap;
    Map<Integer, Node> map = new HashMap<>();
    Node head = new Node(0,0), tail = new Node(0,0);
    
    Problem01_LRUCache(int capacity) { cap = capacity; head.next = tail; tail.prev = head; }
    
    int get(int key) {
        if (!map.containsKey(key)) return -1;
        Node n = map.get(key); remove(n); insertFront(n); return n.val;
    }
    
    void put(int key, int value) {
        if (map.containsKey(key)) remove(map.get(key));
        Node n = new Node(key, value); map.put(key, n); insertFront(n);
        if (map.size() > cap) { Node lru = tail.prev; remove(lru); map.remove(lru.key); }
    }
    
    void remove(Node n) { n.prev.next = n.next; n.next.prev = n.prev; }
    void insertFront(Node n) { n.next = head.next; n.prev = head; head.next.prev = n; head.next = n; }
    
    public static void main(String[] args) {
        Problem01_LRUCache cache = new Problem01_LRUCache(2);
        cache.put(1,1); cache.put(2,2);
        System.out.println(cache.get(1)); // 1
        cache.put(3,3);
        System.out.println(cache.get(2)); // -1
    }
}
