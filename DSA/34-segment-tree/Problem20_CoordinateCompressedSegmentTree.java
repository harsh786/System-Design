package segmenttree;

import java.util.*;

/**
 * Problem 20: Coordinate Compressed Segment Tree
 * 
 * Approach: Compress coordinates to [0, k) range, then use standard segment tree.
 * Useful when values are large but count of distinct values is small.
 * 
 * Time Complexity: O(n log n) for sort + O(n log k) for operations
 * Space Complexity: O(k)
 */
public class Problem20_CoordinateCompressedSegmentTree {
    
    private int[] tree;
    private int size;
    private int[] sorted;
    
    public Problem20_CoordinateCompressedSegmentTree(int[] values) {
        TreeSet<Integer> set = new TreeSet<>();
        for (int v : values) set.add(v);
        sorted = new int[set.size()];
        int i = 0;
        for (int v : set) sorted[i++] = v;
        size = sorted.length;
        tree = new int[4 * size];
    }
    
    private int compress(int val) { return Arrays.binarySearch(sorted, val); }
    
    public void update(int val, int delta) { update(1, 0, size - 1, compress(val), delta); }
    
    private void update(int node, int s, int e, int idx, int delta) {
        if (s == e) { tree[node] += delta; return; }
        int mid = (s + e) / 2;
        if (idx <= mid) update(2 * node, s, mid, idx, delta);
        else update(2 * node + 1, mid + 1, e, idx, delta);
        tree[node] = tree[2 * node] + tree[2 * node + 1];
    }
    
    // Count elements in original value range [lo, hi]
    public int query(int lo, int hi) {
        int l = lowerBound(lo), r = upperBound(hi);
        if (l > r) return 0;
        return query(1, 0, size - 1, l, r);
    }
    
    private int query(int node, int s, int e, int l, int r) {
        if (r < s || e < l) return 0;
        if (l <= s && e <= r) return tree[node];
        int mid = (s + e) / 2;
        return query(2 * node, s, mid, l, r) + query(2 * node + 1, mid + 1, e, l, r);
    }
    
    private int lowerBound(int val) {
        int lo = 0, hi = size;
        while (lo < hi) { int mid = (lo + hi) / 2; if (sorted[mid] < val) lo = mid + 1; else hi = mid; }
        return lo;
    }
    
    private int upperBound(int val) {
        int lo = 0, hi = size;
        while (lo < hi) { int mid = (lo + hi) / 2; if (sorted[mid] <= val) lo = mid + 1; else hi = mid; }
        return lo - 1;
    }
    
    public static void main(String[] args) {
        int[] values = {100, 500, 200, 800, 300};
        Problem20_CoordinateCompressedSegmentTree st = new Problem20_CoordinateCompressedSegmentTree(values);
        for (int v : values) st.update(v, 1);
        System.out.println(st.query(100, 300)); // 3 (100,200,300)
        System.out.println(st.query(400, 900)); // 2 (500,800)
    }
}
