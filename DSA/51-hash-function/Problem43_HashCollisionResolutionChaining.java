import java.util.*;

public class Problem43_HashCollisionResolutionChaining {
    private static final int SIZE = 16;
    private LinkedList<int[]>[] table;

    @SuppressWarnings("unchecked")
    public Problem43_HashCollisionResolutionChaining() {
        table = new LinkedList[SIZE];
        for (int i = 0; i < SIZE; i++) table[i] = new LinkedList<>();
    }

    private int hash(int key) { return key & (SIZE - 1); }

    public void put(int key, int value) {
        int idx = hash(key);
        for (int[] pair : table[idx]) { if (pair[0] == key) { pair[1] = value; return; } }
        table[idx].add(new int[]{key, value});
    }

    public int get(int key) {
        for (int[] pair : table[hash(key)]) if (pair[0] == key) return pair[1];
        return -1;
    }

    public void remove(int key) { table[hash(key)].removeIf(p -> p[0] == key); }

    public static void main(String[] args) {
        Problem43_HashCollisionResolutionChaining ht = new Problem43_HashCollisionResolutionChaining();
        ht.put(1, 10); ht.put(17, 20); // same bucket (1 & 15 == 17 & 15 == 1)
        System.out.println("Get 1: " + ht.get(1)); // 10
        System.out.println("Get 17: " + ht.get(17)); // 20
    }
}
