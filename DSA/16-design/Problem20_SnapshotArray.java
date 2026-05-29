import java.util.*;

/**
 * Problem 20: Snapshot Array
 * 
 * API Contract:
 * - set(index, val): Set value at index
 * - snap(): Take snapshot, return snap_id
 * - get(index, snap_id): Get value at index for given snapshot
 * 
 * Complexity: set O(1), snap O(1), get O(log S) where S = snapshots for that index
 * Data Structure: Array of TreeMaps (snap_id -> value) per index
 * 
 * Production Analogy: MVCC in databases (PostgreSQL), copy-on-write file systems (ZFS),
 * Git commits, versioned configuration stores
 */
public class Problem20_SnapshotArray {

    static class SnapshotArray {
        private List<TreeMap<Integer, Integer>> data;
        private int snapId;

        public SnapshotArray(int length) {
            data = new ArrayList<>();
            for (int i = 0; i < length; i++) {
                TreeMap<Integer, Integer> tm = new TreeMap<>();
                tm.put(0, 0);
                data.add(tm);
            }
            snapId = 0;
        }

        public void set(int index, int val) {
            data.get(index).put(snapId, val);
        }

        public int snap() {
            return snapId++;
        }

        public int get(int index, int snap_id) {
            return data.get(index).floorEntry(snap_id).getValue();
        }
    }

    public static void main(String[] args) {
        SnapshotArray sa = new SnapshotArray(3);
        sa.set(0, 5);
        int s0 = sa.snap(); // 0
        sa.set(0, 6);
        assert sa.get(0, s0) == 5;
        assert sa.get(0, s0 + 1) == 6; // but snap 1 not taken yet, still returns latest

        // Multiple snapshots
        SnapshotArray sa2 = new SnapshotArray(2);
        sa2.set(0, 1);
        int id0 = sa2.snap();
        sa2.set(0, 2);
        int id1 = sa2.snap();
        sa2.set(0, 3);
        assert sa2.get(0, id0) == 1;
        assert sa2.get(0, id1) == 2;

        System.out.println("All tests passed!");
    }
}
