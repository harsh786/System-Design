/**
 * Problem 21: LRU Cache
 * 
 * Approach: HashMap + Doubly Linked List. Map for O(1) lookup, DLL for O(1) eviction.
 * Time Complexity: O(1) for get and put
 * Space Complexity: O(capacity)
 * 
 * Production Analogy: Redis-style cache eviction - least recently used entries are
 * evicted when memory pressure hits the configured maxmemory limit.
 */
import java.util.*;

public class Problem21_LRUCache {
    static class DLinkedNode {
        int key, value;
        DLinkedNode prev, next;
        DLinkedNode() {}
        DLinkedNode(int k, int v) { key = k; value = v; }
    }

    static class LRUCache {
        private Map<Integer, DLinkedNode> cache = new HashMap<>();
        private int capacity;
        private DLinkedNode head = new DLinkedNode(), tail = new DLinkedNode();

        public LRUCache(int capacity) {
            this.capacity = capacity;
            head.next = tail; tail.prev = head;
        }

        public int get(int key) {
            DLinkedNode node = cache.get(key);
            if (node == null) return -1;
            moveToHead(node);
            return node.value;
        }

        public void put(int key, int value) {
            DLinkedNode node = cache.get(key);
            if (node != null) { node.value = value; moveToHead(node); }
            else {
                DLinkedNode newNode = new DLinkedNode(key, value);
                cache.put(key, newNode);
                addToHead(newNode);
                if (cache.size() > capacity) {
                    DLinkedNode removed = tail.prev;
                    removeNode(removed);
                    cache.remove(removed.key);
                }
            }
        }

        private void addToHead(DLinkedNode node) { node.prev=head; node.next=head.next; head.next.prev=node; head.next=node; }
        private void removeNode(DLinkedNode node) { node.prev.next=node.next; node.next.prev=node.prev; }
        private void moveToHead(DLinkedNode node) { removeNode(node); addToHead(node); }
    }

    public static void main(String[] args) {
        LRUCache cache = new LRUCache(2);
        cache.put(1, 1); cache.put(2, 2);
        System.out.println(cache.get(1)); // 1
        cache.put(3, 3); // evicts 2
        System.out.println(cache.get(2)); // -1
        cache.put(4, 4); // evicts 1
        System.out.println(cache.get(1)); // -1
        System.out.println(cache.get(3)); // 3
        System.out.println(cache.get(4)); // 4
    }
}
