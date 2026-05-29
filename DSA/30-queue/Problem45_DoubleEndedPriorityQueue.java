import java.util.*;

public class Problem45_DoubleEndedPriorityQueue {
    TreeMap<Integer, Integer> map = new TreeMap<>();
    void insert(int val) { map.merge(val, 1, Integer::sum); }
    int getMin() { return map.firstKey(); }
    int getMax() { return map.lastKey(); }
    int removeMin() { int k = map.firstKey(); if (map.get(k) == 1) map.remove(k); else map.merge(k, -1, Integer::sum); return k; }
    int removeMax() { int k = map.lastKey(); if (map.get(k) == 1) map.remove(k); else map.merge(k, -1, Integer::sum); return k; }
    boolean isEmpty() { return map.isEmpty(); }
    public static void main(String[] args) {
        Problem45_DoubleEndedPriorityQueue depq = new Problem45_DoubleEndedPriorityQueue();
        depq.insert(5); depq.insert(1); depq.insert(9); depq.insert(3);
        System.out.println(depq.removeMin()); // 1
        System.out.println(depq.removeMax()); // 9
        System.out.println(depq.getMin()); // 3
    }
}
