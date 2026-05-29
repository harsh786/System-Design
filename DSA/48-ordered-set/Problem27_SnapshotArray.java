import java.util.*;

public class Problem27_SnapshotArray {
    // LC 1146: Array with set, snap, get(index, snap_id)
    TreeMap<Integer, Integer>[] arr;
    int snapId;

    @SuppressWarnings("unchecked")
    public Problem27_SnapshotArray(int length) {
        arr = new TreeMap[length];
        for (int i = 0; i < length; i++) {
            arr[i] = new TreeMap<>();
            arr[i].put(0, 0);
        }
        snapId = 0;
    }

    public void set(int index, int val) { arr[index].put(snapId, val); }
    public int snap() { return snapId++; }
    public int get(int index, int snap_id) { return arr[index].floorEntry(snap_id).getValue(); }

    public static void main(String[] args) {
        Problem27_SnapshotArray sa = new Problem27_SnapshotArray(3);
        sa.set(0, 5);
        System.out.println(sa.snap()); // 0
        sa.set(0, 6);
        System.out.println(sa.get(0, 0)); // 5
    }
}
