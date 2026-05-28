/**
 * Problem 36: All O(1) Data Structure - Inc/Dec/GetMaxKey/GetMinKey all O(1)
 * 
 * Approach: Doubly linked list of count buckets + HashMap<key, bucket>.
 * Each bucket holds all keys with that count.
 * Time Complexity: O(1) for all operations
 * Space Complexity: O(n)
 * 
 * Production Analogy: Real-time analytics dashboard tracking request frequencies
 * with instant access to most/least popular endpoints.
 */
import java.util.*;

public class Problem36_AllO1DataStructure {
    static class AllOne {
        static class Bucket {
            int count;
            Set<String> keys = new LinkedHashSet<>();
            Bucket prev, next;
            Bucket(int c) { count = c; }
        }

        Map<String, Bucket> keyBucket = new HashMap<>();
        Bucket head = new Bucket(Integer.MIN_VALUE), tail = new Bucket(Integer.MAX_VALUE);

        public AllOne() { head.next = tail; tail.prev = head; }

        private Bucket addBucketAfter(Bucket prev, int count) {
            Bucket b = new Bucket(count);
            b.prev = prev; b.next = prev.next;
            prev.next.prev = b; prev.next = b;
            return b;
        }

        private void removeBucket(Bucket b) { b.prev.next = b.next; b.next.prev = b.prev; }

        public void inc(String key) {
            if (!keyBucket.containsKey(key)) {
                Bucket first = head.next;
                if (first.count != 1) first = addBucketAfter(head, 1);
                first.keys.add(key);
                keyBucket.put(key, first);
            } else {
                Bucket curr = keyBucket.get(key);
                Bucket next = curr.next;
                if (next.count != curr.count + 1) next = addBucketAfter(curr, curr.count + 1);
                next.keys.add(key);
                keyBucket.put(key, next);
                curr.keys.remove(key);
                if (curr.keys.isEmpty()) removeBucket(curr);
            }
        }

        public void dec(String key) {
            Bucket curr = keyBucket.get(key);
            if (curr.count == 1) {
                keyBucket.remove(key);
            } else {
                Bucket prev = curr.prev;
                if (prev.count != curr.count - 1) prev = addBucketAfter(curr.prev, curr.count - 1);
                prev.keys.add(key);
                keyBucket.put(key, prev);
            }
            curr.keys.remove(key);
            if (curr.keys.isEmpty()) removeBucket(curr);
        }

        public String getMaxKey() { return tail.prev == head ? "" : tail.prev.keys.iterator().next(); }
        public String getMinKey() { return head.next == tail ? "" : head.next.keys.iterator().next(); }
    }

    public static void main(String[] args) {
        AllOne ao = new AllOne();
        ao.inc("hello"); ao.inc("hello");
        ao.inc("world");
        System.out.println(ao.getMaxKey()); // hello
        System.out.println(ao.getMinKey()); // world
        ao.inc("world"); ao.inc("world");
        System.out.println(ao.getMaxKey()); // world
        ao.dec("world"); ao.dec("world");
        System.out.println(ao.getMaxKey()); // hello
    }
}
