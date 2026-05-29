import java.util.*;

public class Problem11_DesignHashMap {
    private static final int SIZE = 1009;
    private LinkedList<int[]>[] buckets;

    @SuppressWarnings("unchecked")
    public Problem11_DesignHashMap() {
        buckets = new LinkedList[SIZE];
    }

    private int hash(int key) { return key % SIZE; }

    public void put(int key, int value) {
        int idx = hash(key);
        if (buckets[idx] == null) buckets[idx] = new LinkedList<>();
        for (int[] pair : buckets[idx]) { if (pair[0] == key) { pair[1] = value; return; } }
        buckets[idx].add(new int[]{key, value});
    }

    public int get(int key) {
        int idx = hash(key);
        if (buckets[idx] == null) return -1;
        for (int[] pair : buckets[idx]) if (pair[0] == key) return pair[1];
        return -1;
    }

    public void remove(int key) {
        int idx = hash(key);
        if (buckets[idx] == null) return;
        buckets[idx].removeIf(pair -> pair[0] == key);
    }

    public static void main(String[] args) {
        Problem11_DesignHashMap map = new Problem11_DesignHashMap();
        map.put(1, 1); map.put(2, 2);
        System.out.println(map.get(1)); // 1
        map.remove(2);
        System.out.println(map.get(2)); // -1
    }
}
