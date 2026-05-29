import java.util.*;

public class Problem45_CuckooHashing {
    private static final int SIZE = 16;
    private static final int MAX_KICKS = 500;
    private Integer[] table1 = new Integer[SIZE], table2 = new Integer[SIZE];
    private int[] val1 = new int[SIZE], val2 = new int[SIZE];

    private int h1(int key) { return key & (SIZE - 1); }
    private int h2(int key) { return (key >>> 4) & (SIZE - 1); }

    public boolean put(int key, int value) {
        int idx = h1(key);
        if (table1[idx] != null && table1[idx] == key) { val1[idx] = value; return true; }
        idx = h2(key);
        if (table2[idx] != null && table2[idx] == key) { val2[idx] = value; return true; }
        int curKey = key, curVal = value;
        for (int i = 0; i < MAX_KICKS; i++) {
            int pos = h1(curKey);
            if (table1[pos] == null) { table1[pos] = curKey; val1[pos] = curVal; return true; }
            int tmpK = table1[pos]; int tmpV = val1[pos];
            table1[pos] = curKey; val1[pos] = curVal; curKey = tmpK; curVal = tmpV;
            pos = h2(curKey);
            if (table2[pos] == null) { table2[pos] = curKey; val2[pos] = curVal; return true; }
            tmpK = table2[pos]; tmpV = val2[pos];
            table2[pos] = curKey; val2[pos] = curVal; curKey = tmpK; curVal = tmpV;
        }
        return false; // need rehash
    }

    public int get(int key) {
        int idx = h1(key);
        if (table1[idx] != null && table1[idx] == key) return val1[idx];
        idx = h2(key);
        if (table2[idx] != null && table2[idx] == key) return val2[idx];
        return -1;
    }

    public static void main(String[] args) {
        Problem45_CuckooHashing sol = new Problem45_CuckooHashing();
        sol.put(5, 50); sol.put(21, 210); sol.put(37, 370);
        System.out.println("Get 5: " + sol.get(5));
        System.out.println("Get 21: " + sol.get(21));
        System.out.println("Get 37: " + sol.get(37));
    }
}
