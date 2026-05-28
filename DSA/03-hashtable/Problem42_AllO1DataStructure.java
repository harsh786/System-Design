import java.util.*;

/**
 * Problem 42: All O(1) Data Structure
 * Inc/Dec key count, getMaxKey, getMinKey all in O(1).
 *
 * Approach: Doubly linked list of count buckets + HashMap(key -> bucket).
 * Each bucket holds all keys with that count.
 *
 * Time Complexity: O(1) all operations
 * Space Complexity: O(n)
 *
 * Production Analogy: Like real-time leaderboard tracking in gaming or
 * hot key detection in distributed caches with O(1) min/max access.
 */
public class Problem42_AllO1DataStructure {
    private class Bucket {
        int count;
        Set<String> keys = new LinkedHashSet<>();
        Bucket prev, next;
        Bucket(int c) { count = c; }
    }

    private Map<String, Bucket> keyToBucket = new HashMap<>();
    private Bucket head = new Bucket(Integer.MIN_VALUE), tail = new Bucket(Integer.MAX_VALUE);

    public Problem42_AllO1DataStructure() { head.next = tail; tail.prev = head; }

    private Bucket addBucketAfter(Bucket prev, int count) {
        Bucket b = new Bucket(count);
        b.prev = prev; b.next = prev.next;
        prev.next.prev = b; prev.next = b;
        return b;
    }

    private void removeBucket(Bucket b) { b.prev.next = b.next; b.next.prev = b.prev; }

    public void inc(String key) {
        if (keyToBucket.containsKey(key)) {
            Bucket cur = keyToBucket.get(key);
            Bucket next = (cur.next.count == cur.count + 1) ? cur.next : addBucketAfter(cur, cur.count + 1);
            next.keys.add(key);
            keyToBucket.put(key, next);
            cur.keys.remove(key);
            if (cur.keys.isEmpty()) removeBucket(cur);
        } else {
            Bucket first = (head.next.count == 1) ? head.next : addBucketAfter(head, 1);
            first.keys.add(key);
            keyToBucket.put(key, first);
        }
    }

    public void dec(String key) {
        Bucket cur = keyToBucket.get(key);
        if (cur.count == 1) {
            keyToBucket.remove(key);
        } else {
            Bucket prev = (cur.prev.count == cur.count - 1) ? cur.prev : addBucketAfter(cur.prev, cur.count - 1);
            prev.keys.add(key);
            keyToBucket.put(key, prev);
        }
        cur.keys.remove(key);
        if (cur.keys.isEmpty()) removeBucket(cur);
    }

    public String getMaxKey() { return tail.prev == head ? "" : tail.prev.keys.iterator().next(); }
    public String getMinKey() { return head.next == tail ? "" : head.next.keys.iterator().next(); }

    public static void main(String[] args) {
        Problem42_AllO1DataStructure ds = new Problem42_AllO1DataStructure();
        ds.inc("hello"); ds.inc("hello");
        ds.inc("world");
        System.out.println(ds.getMaxKey()); // hello
        System.out.println(ds.getMinKey()); // world
        ds.inc("world"); ds.inc("world");
        System.out.println(ds.getMaxKey()); // world
        ds.dec("world"); ds.dec("world"); ds.dec("world");
        System.out.println(ds.getMaxKey()); // hello
    }
}
