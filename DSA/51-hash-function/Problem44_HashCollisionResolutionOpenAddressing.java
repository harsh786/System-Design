import java.util.*;

public class Problem44_HashCollisionResolutionOpenAddressing {
    private static final int SIZE = 32;
    private Integer[] keys = new Integer[SIZE];
    private int[] values = new int[SIZE];
    private boolean[] deleted = new boolean[SIZE];

    private int hash(int key) { return key & (SIZE - 1); }

    public void put(int key, int value) {
        int idx = hash(key);
        while (keys[idx] != null && keys[idx] != key && !deleted[idx]) idx = (idx + 1) & (SIZE - 1);
        keys[idx] = key; values[idx] = value; deleted[idx] = false;
    }

    public int get(int key) {
        int idx = hash(key);
        while (keys[idx] != null) {
            if (keys[idx] == key && !deleted[idx]) return values[idx];
            idx = (idx + 1) & (SIZE - 1);
        }
        return -1;
    }

    public void remove(int key) {
        int idx = hash(key);
        while (keys[idx] != null) {
            if (keys[idx] == key && !deleted[idx]) { deleted[idx] = true; return; }
            idx = (idx + 1) & (SIZE - 1);
        }
    }

    public static void main(String[] args) {
        Problem44_HashCollisionResolutionOpenAddressing ht = new Problem44_HashCollisionResolutionOpenAddressing();
        ht.put(1, 100); ht.put(33, 200); // collision with linear probing
        System.out.println("Get 1: " + ht.get(1)); // 100
        System.out.println("Get 33: " + ht.get(33)); // 200
        ht.remove(1);
        System.out.println("Get 1 after remove: " + ht.get(1)); // -1
        System.out.println("Get 33 after remove of 1: " + ht.get(33)); // 200
    }
}
