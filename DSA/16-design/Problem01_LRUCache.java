import java.util.*;

/**
 * Problem 1: LRU Cache (Least Recently Used)
 * 
 * API Contract:
 * - get(key): Return value if key exists, else -1. Marks as recently used.
 * - put(key, value): Insert/update key-value. Evicts LRU item if at capacity.
 * 
 * Complexity: O(1) for both get and put
 * Data Structures: HashMap + Doubly Linked List
 * 
 * Production Analogy: CPU cache, CDN cache eviction, database buffer pool,
 * browser cache, Redis maxmemory-policy allkeys-lru
 */
public class Problem01_LRUCache {

    static class LRUCache {
        private class Node {
            int key, value;
            Node prev, next;
            Node(int k, int v) { key = k; value = v; }
        }

        private int capacity;
        private Map<Integer, Node> map;
        private Node head, tail; // dummy sentinel nodes

        public LRUCache(int capacity) {
            this.capacity = capacity;
            map = new HashMap<>();
            head = new Node(0, 0);
            tail = new Node(0, 0);
            head.next = tail;
            tail.prev = head;
        }

        public int get(int key) {
            if (!map.containsKey(key)) return -1;
            Node node = map.get(key);
            remove(node);
            insertAtHead(node);
            return node.value;
        }

        public void put(int key, int value) {
            if (map.containsKey(key)) {
                Node node = map.get(key);
                node.value = value;
                remove(node);
                insertAtHead(node);
            } else {
                if (map.size() == capacity) {
                    Node lru = tail.prev;
                    remove(lru);
                    map.remove(lru.key);
                }
                Node node = new Node(key, value);
                map.put(key, node);
                insertAtHead(node);
            }
        }

        private void remove(Node node) {
            node.prev.next = node.next;
            node.next.prev = node.prev;
        }

        private void insertAtHead(Node node) {
            node.next = head.next;
            node.prev = head;
            head.next.prev = node;
            head.next = node;
        }
    }

    public static void main(String[] args) {
        LRUCache cache = new LRUCache(2);
        cache.put(1, 1);
        cache.put(2, 2);
        assert cache.get(1) == 1 : "Test 1 failed";
        cache.put(3, 3); // evicts key 2
        assert cache.get(2) == -1 : "Test 2 failed";
        cache.put(4, 4); // evicts key 1
        assert cache.get(1) == -1 : "Test 3 failed";
        assert cache.get(3) == 3 : "Test 4 failed";
        assert cache.get(4) == 4 : "Test 5 failed";

        // Edge: capacity 1
        LRUCache c1 = new LRUCache(1);
        c1.put(1, 1);
        c1.put(2, 2);
        assert c1.get(1) == -1;
        assert c1.get(2) == 2;

        // Edge: update existing key
        LRUCache c2 = new LRUCache(2);
        c2.put(1, 1);
        c2.put(1, 10);
        assert c2.get(1) == 10;

        System.out.println("All tests passed!");
    }
}
