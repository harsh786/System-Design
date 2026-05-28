import java.util.*;

/**
 * Problem 37: Snapshot Array
 * 
 * Support set(index, val), snap(), get(index, snap_id).
 * 
 * Approach: Each index stores list of (snap_id, val). Binary search on get.
 * 
 * Time: set O(1), snap O(1), get O(log S), Space: O(S) where S = total sets
 * 
 * Production Analogy: MVCC (Multi-Version Concurrency Control) in databases —
 * reading a value as of a specific transaction/snapshot ID.
 */
public class Problem37_SnapshotArray {
    private List<int[]>[] data; // each index -> list of [snap_id, val]
    private int snapId;

    @SuppressWarnings("unchecked")
    public Problem37_SnapshotArray(int length) {
        data = new ArrayList[length];
        for (int i = 0; i < length; i++) {
            data[i] = new ArrayList<>();
            data[i].add(new int[]{0, 0});
        }
        snapId = 0;
    }

    public void set(int index, int val) {
        List<int[]> list = data[index];
        if (list.get(list.size() - 1)[0] == snapId)
            list.get(list.size() - 1)[1] = val;
        else
            list.add(new int[]{snapId, val});
    }

    public int snap() { return snapId++; }

    public int get(int index, int snap_id) {
        List<int[]> list = data[index];
        int lo = 0, hi = list.size() - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo + 1) / 2;
            if (list.get(mid)[0] <= snap_id) lo = mid;
            else hi = mid - 1;
        }
        return list.get(lo)[1];
    }

    public static void main(String[] args) {
        Problem37_SnapshotArray sa = new Problem37_SnapshotArray(3);
        sa.set(0, 5);
        System.out.println(sa.snap()); // 0
        sa.set(0, 6);
        System.out.println(sa.get(0, 0)); // 5
        System.out.println(sa.get(0, 1)); // 6 (snap 1 not taken yet but current)
        System.out.println(sa.snap()); // 1
        System.out.println(sa.get(0, 1)); // 6
    }
}
