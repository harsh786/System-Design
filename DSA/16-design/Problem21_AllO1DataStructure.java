import java.util.*;

/**
 * Problem 21: All O(1) Data Structure
 * 
 * API Contract:
 * - inc(key): Increment count of key
 * - dec(key): Decrement count of key (remove if 0)
 * - getMaxKey(): Return key with max count
 * - getMinKey(): Return key with min count
 * 
 * Complexity: O(1) for all operations
 * Data Structure: Doubly linked list of count buckets + HashMap key->bucket
 * 
 * Production Analogy: Real-time trending topics, leaderboard with O(1) min/max,
 * frequency-based cache eviction metadata
 */
public class Problem21_AllO1DataStructure {

    static class AllOne {
        private class Bucket {
            int count;
            Set<String> keys;
            Bucket prev, next;
            Bucket(int c) { count = c; keys = new LinkedHashSet<>(); }
        }

        private Map<String, Bucket> keyToBucket;
        private Bucket head, tail; // sentinels

        public AllOne() {
            keyToBucket = new HashMap<>();
            head = new Bucket(Integer.MIN_VALUE);
            tail = new Bucket(Integer.MAX_VALUE);
            head.next = tail;
            tail.prev = head;
        }

        public void inc(String key) {
            if (!keyToBucket.containsKey(key)) {
                // Add to bucket with count 1
                Bucket first = head.next;
                if (first.count != 1) {
                    first = addBucketAfter(new Bucket(1), head);
                }
                first.keys.add(key);
                keyToBucket.put(key, first);
            } else {
                Bucket cur = keyToBucket.get(key);
                Bucket next = cur.next;
                if (next.count != cur.count + 1) {
                    next = addBucketAfter(new Bucket(cur.count + 1), cur);
                }
                next.keys.add(key);
                keyToBucket.put(key, next);
                cur.keys.remove(key);
                if (cur.keys.isEmpty()) removeBucket(cur);
            }
        }

        public void dec(String key) {
            Bucket cur = keyToBucket.get(key);
            if (cur.count == 1) {
                keyToBucket.remove(key);
            } else {
                Bucket prev = cur.prev;
                if (prev.count != cur.count - 1) {
                    prev = addBucketAfter(new Bucket(cur.count - 1), cur.prev);
                }
                prev.keys.add(key);
                keyToBucket.put(key, prev);
            }
            cur.keys.remove(key);
            if (cur.keys.isEmpty()) removeBucket(cur);
        }

        public String getMaxKey() {
            return tail.prev == head ? "" : tail.prev.keys.iterator().next();
        }

        public String getMinKey() {
            return head.next == tail ? "" : head.next.keys.iterator().next();
        }

        private Bucket addBucketAfter(Bucket bucket, Bucket prev) {
            bucket.prev = prev;
            bucket.next = prev.next;
            prev.next.prev = bucket;
            prev.next = bucket;
            return bucket;
        }

        private void removeBucket(Bucket bucket) {
            bucket.prev.next = bucket.next;
            bucket.next.prev = bucket.prev;
        }
    }

    public static void main(String[] args) {
        AllOne ao = new AllOne();
        ao.inc("a"); ao.inc("b"); ao.inc("b");
        assert ao.getMaxKey().equals("b");
        assert ao.getMinKey().equals("a");
        ao.dec("b"); ao.dec("b");
        assert ao.getMaxKey().equals("a");
        ao.dec("a");
        assert ao.getMaxKey().equals("");
        assert ao.getMinKey().equals("");

        System.out.println("All tests passed!");
    }
}
