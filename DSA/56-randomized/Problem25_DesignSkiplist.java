import java.util.*;

public class Problem25_DesignSkiplist {
    static final int MAX_LEVEL = 16;
    static final double P = 0.5;
    static Random rand = new Random();

    static class Node {
        int val; Node[] next;
        Node(int v, int level) { val = v; next = new Node[level + 1]; }
    }

    Node head = new Node(Integer.MIN_VALUE, MAX_LEVEL);
    int level = 0;

    int randomLevel() { int l = 0; while (rand.nextDouble() < P && l < MAX_LEVEL) l++; return l; }

    public boolean search(int target) {
        Node cur = head;
        for (int i = level; i >= 0; i--) while (cur.next[i] != null && cur.next[i].val < target) cur = cur.next[i];
        cur = cur.next[0];
        return cur != null && cur.val == target;
    }

    public void add(int num) {
        Node[] update = new Node[MAX_LEVEL + 1];
        Node cur = head;
        for (int i = level; i >= 0; i--) { while (cur.next[i] != null && cur.next[i].val < num) cur = cur.next[i]; update[i] = cur; }
        int newLevel = randomLevel();
        if (newLevel > level) { for (int i = level+1; i <= newLevel; i++) update[i] = head; level = newLevel; }
        Node node = new Node(num, newLevel);
        for (int i = 0; i <= newLevel; i++) { node.next[i] = update[i].next[i]; update[i].next[i] = node; }
    }

    public boolean erase(int num) {
        Node[] update = new Node[MAX_LEVEL + 1];
        Node cur = head;
        for (int i = level; i >= 0; i--) { while (cur.next[i] != null && cur.next[i].val < num) cur = cur.next[i]; update[i] = cur; }
        cur = cur.next[0];
        if (cur == null || cur.val != num) return false;
        for (int i = 0; i <= level; i++) { if (update[i].next[i] != cur) break; update[i].next[i] = cur.next[i]; }
        while (level > 0 && head.next[level] == null) level--;
        return true;
    }

    public static void main(String[] args) {
        Problem25_DesignSkiplist sl = new Problem25_DesignSkiplist();
        sl.add(1); sl.add(2); sl.add(3);
        System.out.println(sl.search(1)); // true
        System.out.println(sl.erase(2)); // true
        System.out.println(sl.search(2)); // false
    }
}
