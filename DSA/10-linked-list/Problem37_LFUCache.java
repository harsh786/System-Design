/**
 * Problem 37: LFU Cache
 * 
 * Approach: Two HashMaps (key->node, freq->DLL) + minFreq tracker.
 * Time Complexity: O(1) for get and put
 * Space Complexity: O(capacity)
 * 
 * Production Analogy: CDN cache eviction - least frequently accessed content
 * is purged first; ties broken by LRU within same frequency.
 */
import java.util.*;

public class Problem37_LFUCache {
    static class Node {
        int key, val, freq;
        Node prev, next;
        Node(int k, int v) { key=k; val=v; freq=1; }
    }

    static class DLL {
        Node head = new Node(0,0), tail = new Node(0,0);
        int size;
        DLL() { head.next=tail; tail.prev=head; }
        void addFirst(Node n) { n.next=head.next; n.prev=head; head.next.prev=n; head.next=n; size++; }
        Node removeLast() { Node n=tail.prev; remove(n); return n; }
        void remove(Node n) { n.prev.next=n.next; n.next.prev=n.prev; size--; }
    }

    static class LFUCache {
        int capacity, minFreq;
        Map<Integer, Node> keyMap = new HashMap<>();
        Map<Integer, DLL> freqMap = new HashMap<>();

        public LFUCache(int capacity) { this.capacity = capacity; }

        public int get(int key) {
            Node n = keyMap.get(key);
            if (n == null) return -1;
            updateFreq(n);
            return n.val;
        }

        public void put(int key, int value) {
            if (capacity == 0) return;
            Node n = keyMap.get(key);
            if (n != null) { n.val = value; updateFreq(n); return; }
            if (keyMap.size() == capacity) {
                DLL dll = freqMap.get(minFreq);
                Node removed = dll.removeLast();
                keyMap.remove(removed.key);
            }
            Node newNode = new Node(key, value);
            keyMap.put(key, newNode);
            freqMap.computeIfAbsent(1, k -> new DLL()).addFirst(newNode);
            minFreq = 1;
        }

        private void updateFreq(Node n) {
            DLL dll = freqMap.get(n.freq);
            dll.remove(n);
            if (dll.size == 0 && n.freq == minFreq) minFreq++;
            n.freq++;
            freqMap.computeIfAbsent(n.freq, k -> new DLL()).addFirst(n);
        }
    }

    public static void main(String[] args) {
        LFUCache cache = new LFUCache(2);
        cache.put(1, 1); cache.put(2, 2);
        System.out.println(cache.get(1)); // 1
        cache.put(3, 3); // evicts key 2
        System.out.println(cache.get(2)); // -1
        System.out.println(cache.get(3)); // 3
        cache.put(4, 4); // evicts key 3
        System.out.println(cache.get(1)); // 1
        System.out.println(cache.get(3)); // -1
        System.out.println(cache.get(4)); // 4
    }
}
