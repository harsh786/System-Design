/**
 * Problem 31: Segment Tree Build and Query
 * 
 * D&C Approach:
 * - BUILD: DIVIDE array at mid, CONQUER build left/right subtrees,
 *   COMBINE by storing aggregate (sum/min/max) at parent
 * - QUERY: If range fully contained, return node value.
 *   Otherwise split query into left/right child ranges.
 * - UPDATE: Navigate to leaf, update, propagate changes up.
 * 
 * Time: Build O(n), Query O(log n), Update O(log n)
 * Space: O(n)
 * 
 * Production Analogy:
 * - Range query engines (time-series databases)
 * - OLAP systems for aggregate queries over ranges
 * - Network bandwidth monitoring (sum/max over time ranges)
 */
public class Problem31_SegmentTreeBuildAndQuery {

    private int[] tree;
    private int n;

    public Problem31_SegmentTreeBuildAndQuery(int[] arr) {
        n = arr.length;
        tree = new int[4 * n];
        build(arr, 1, 0, n - 1);
    }

    private void build(int[] arr, int node, int lo, int hi) {
        if (lo == hi) { tree[node] = arr[lo]; return; }
        int mid = lo + (hi - lo) / 2;
        build(arr, 2 * node, lo, mid);
        build(arr, 2 * node + 1, mid + 1, hi);
        tree[node] = tree[2 * node] + tree[2 * node + 1]; // Sum
    }

    public int query(int l, int r) {
        return query(1, 0, n - 1, l, r);
    }

    private int query(int node, int lo, int hi, int l, int r) {
        if (r < lo || hi < l) return 0; // Out of range
        if (l <= lo && hi <= r) return tree[node]; // Fully contained
        int mid = lo + (hi - lo) / 2;
        return query(2 * node, lo, mid, l, r) + query(2 * node + 1, mid + 1, hi, l, r);
    }

    public void update(int idx, int val) {
        update(1, 0, n - 1, idx, val);
    }

    private void update(int node, int lo, int hi, int idx, int val) {
        if (lo == hi) { tree[node] = val; return; }
        int mid = lo + (hi - lo) / 2;
        if (idx <= mid) update(2 * node, lo, mid, idx, val);
        else update(2 * node + 1, mid + 1, hi, idx, val);
        tree[node] = tree[2 * node] + tree[2 * node + 1];
    }

    public static void main(String[] args) {
        Problem31_SegmentTreeBuildAndQuery st = new Problem31_SegmentTreeBuildAndQuery(new int[]{1,3,5,7,9,11});
        System.out.println(st.query(0, 5)); // 36
        System.out.println(st.query(1, 3)); // 15
        System.out.println(st.query(2, 2)); // 5
        st.update(2, 10);
        System.out.println(st.query(1, 3)); // 20
        System.out.println(st.query(0, 5)); // 41
    }
}
