import java.util.*;

public class Problem46_RobinHoodHashing {
    private static final int SIZE = 32;
    private Integer[] keys = new Integer[SIZE];
    private int[] values = new int[SIZE];
    private int[] dist = new int[SIZE]; // probe distance

    private int hash(int key) { return key & (SIZE - 1); }

    public void put(int key, int value) {
        int idx = hash(key), d = 0;
        int curKey = key, curVal = value;
        while (true) {
            if (keys[idx] == null) { keys[idx] = curKey; values[idx] = curVal; dist[idx] = d; return; }
            if (keys[idx] == curKey) { values[idx] = curVal; return; }
            if (dist[idx] < d) { // rob from the rich
                int tmpK = keys[idx]; int tmpV = values[idx]; int tmpD = dist[idx];
                keys[idx] = curKey; values[idx] = curVal; dist[idx] = d;
                curKey = tmpK; curVal = tmpV; d = tmpD;
            }
            idx = (idx + 1) & (SIZE - 1); d++;
        }
    }

    public int get(int key) {
        int idx = hash(key), d = 0;
        while (keys[idx] != null) {
            if (keys[idx] == key) return values[idx];
            if (dist[idx] < d) return -1;
            idx = (idx + 1) & (SIZE - 1); d++;
        }
        return -1;
    }

    public static void main(String[] args) {
        Problem46_RobinHoodHashing sol = new Problem46_RobinHoodHashing();
        sol.put(1, 10); sol.put(33, 20); sol.put(65, 30);
        System.out.println("Get 1: " + sol.get(1));
        System.out.println("Get 33: " + sol.get(33));
        System.out.println("Get 65: " + sol.get(65));
    }
}
