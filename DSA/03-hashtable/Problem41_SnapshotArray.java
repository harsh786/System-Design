import java.util.*;

/**
 * Problem 41: Snapshot Array
 * Implement array with snap() and get(index, snap_id) operations.
 *
 * Approach: For each index, store a TreeMap<snapId, value>.
 * get() uses floorKey to find value at or before the snap_id.
 *
 * Time Complexity: O(log S) for get where S = snaps, O(1) for set
 * Space Complexity: O(n * S) worst case, but sparse in practice
 *
 * Production Analogy: Like MVCC (Multi-Version Concurrency Control) in databases.
 * Each write creates a new version; reads can access any historical version.
 */
public class Problem41_SnapshotArray {
    private TreeMap<Integer, Integer>[] arr;
    private int snapId = 0;

    public Problem41_SnapshotArray(int length) {
        arr = new TreeMap[length];
        for (int i = 0; i < length; i++) {
            arr[i] = new TreeMap<>();
            arr[i].put(0, 0);
        }
    }

    public void set(int index, int val) { arr[index].put(snapId, val); }
    public int snap() { return snapId++; }
    public int get(int index, int snap_id) { return arr[index].floorEntry(snap_id).getValue(); }

    public static void main(String[] args) {
        Problem41_SnapshotArray sa = new Problem41_SnapshotArray(3);
        sa.set(0, 5);
        System.out.println(sa.snap()); // 0
        sa.set(0, 6);
        System.out.println(sa.get(0, 0)); // 5
        System.out.println(sa.get(0, 1)); // 6 (snap 1 hasn't happened yet but current value)
        System.out.println(sa.snap()); // 1
        System.out.println(sa.get(0, 1)); // 6
    }
}
