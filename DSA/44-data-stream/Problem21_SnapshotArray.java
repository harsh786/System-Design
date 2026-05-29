import java.util.*;

public class Problem21_SnapshotArray {
    // 1146. Snapshot Array.
    
    List<TreeMap<Integer, Integer>> data;
    int snapId = 0;
    
    public Problem21_SnapshotArray() { data = new ArrayList<>(); }
    
    public void init(int length) {
        data = new ArrayList<>();
        for (int i = 0; i < length; i++) {
            TreeMap<Integer, Integer> tm = new TreeMap<>();
            tm.put(0, 0);
            data.add(tm);
        }
    }
    
    public void set(int index, int val) { data.get(index).put(snapId, val); }
    public int snap() { return snapId++; }
    public int get(int index, int snap_id) { return data.get(index).floorEntry(snap_id).getValue(); }
    
    public static void main(String[] args) {
        Problem21_SnapshotArray sol = new Problem21_SnapshotArray();
        sol.init(3);
        sol.set(0, 5);
        int id = sol.snap(); // 0
        sol.set(0, 6);
        System.out.println(sol.get(0, id)); // 5
    }
}
