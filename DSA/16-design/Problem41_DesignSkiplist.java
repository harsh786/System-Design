import java.util.*;

/**
 * Problem 41: Design Skiplist
 * 
 * API Contract:
 * - search(target): Return true if value exists
 * - add(num): Insert value (duplicates allowed)
 * - erase(num): Remove one occurrence. Return true if found.
 * 
 * Complexity: O(log n) average for all operations
 * Data Structure: Multi-level linked list with probabilistic balancing
 * 
 * Production Analogy: Redis sorted sets (zset), LevelDB/RocksDB memtable,
 * concurrent skip list in Java ConcurrentSkipListMap
 */
public class Problem41_DesignSkiplist {

    static class Skiplist {
        private static final int MAX_LEVEL = 16;
        private static final double P = 0.5;
        private Random rand = new Random();

        private class Node {
            int val;
            Node[] next;
            Node(int val, int level) { this.val = val; next = new Node[level + 1]; }
        }

        private Node head;
        private int level;

        public Skiplist() {
            head = new Node(-1, MAX_LEVEL);
            level = 0;
        }

        private int randomLevel() {
            int lvl = 0;
            while (lvl < MAX_LEVEL && rand.nextDouble() < P) lvl++;
            return lvl;
        }

        public boolean search(int target) {
            Node cur = head;
            for (int i = level; i >= 0; i--) {
                while (cur.next[i] != null && cur.next[i].val < target)
                    cur = cur.next[i];
            }
            cur = cur.next[0];
            return cur != null && cur.val == target;
        }

        public void add(int num) {
            Node[] update = new Node[MAX_LEVEL + 1];
            Node cur = head;
            for (int i = level; i >= 0; i--) {
                while (cur.next[i] != null && cur.next[i].val < num)
                    cur = cur.next[i];
                update[i] = cur;
            }
            int newLevel = randomLevel();
            if (newLevel > level) {
                for (int i = level + 1; i <= newLevel; i++) update[i] = head;
                level = newLevel;
            }
            Node newNode = new Node(num, newLevel);
            for (int i = 0; i <= newLevel; i++) {
                newNode.next[i] = update[i].next[i];
                update[i].next[i] = newNode;
            }
        }

        public boolean erase(int num) {
            Node[] update = new Node[MAX_LEVEL + 1];
            Node cur = head;
            for (int i = level; i >= 0; i--) {
                while (cur.next[i] != null && cur.next[i].val < num)
                    cur = cur.next[i];
                update[i] = cur;
            }
            cur = cur.next[0];
            if (cur == null || cur.val != num) return false;
            for (int i = 0; i <= level; i++) {
                if (update[i].next[i] != cur) break;
                update[i].next[i] = cur.next[i];
            }
            while (level > 0 && head.next[level] == null) level--;
            return true;
        }
    }

    public static void main(String[] args) {
        Skiplist sl = new Skiplist();
        sl.add(1); sl.add(2); sl.add(3);
        assert sl.search(1);
        assert !sl.search(4);
        sl.add(4);
        assert sl.search(4);
        assert sl.erase(1);
        assert !sl.search(1);
        assert !sl.erase(1);

        // Duplicates
        sl.add(5); sl.add(5);
        assert sl.erase(5);
        assert sl.search(5); // second copy still there

        System.out.println("All tests passed!");
    }
}
