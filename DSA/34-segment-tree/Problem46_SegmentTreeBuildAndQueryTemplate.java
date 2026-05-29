package segmenttree;

/**
 * Problem 46: Segment Tree Build and Query Template
 * 
 * A clean, reusable segment tree template for sum queries with point updates.
 * 
 * Time Complexity: O(n) build, O(log n) update/query
 * Space Complexity: O(n)
 */
public class Problem46_SegmentTreeBuildAndQueryTemplate {
    
    private long[] tree;
    private int n;
    
    public Problem46_SegmentTreeBuildAndQueryTemplate(int[] arr) {
        n = arr.length; tree = new long[4 * n];
        build(1, 0, n - 1, arr);
    }
    
    private void build(int o, int s, int e, int[] arr) {
        if (s == e) { tree[o] = arr[s]; return; }
        int mid = (s + e) / 2;
        build(2*o, s, mid, arr); build(2*o+1, mid+1, e, arr);
        tree[o] = tree[2*o] + tree[2*o+1];
    }
    
    public void pointUpdate(int idx, int val) { pointUpdate(1, 0, n-1, idx, val); }
    
    private void pointUpdate(int o, int s, int e, int idx, int val) {
        if (s == e) { tree[o] = val; return; }
        int mid = (s + e) / 2;
        if (idx <= mid) pointUpdate(2*o, s, mid, idx, val);
        else pointUpdate(2*o+1, mid+1, e, idx, val);
        tree[o] = tree[2*o] + tree[2*o+1];
    }
    
    public long rangeQuery(int l, int r) { return rangeQuery(1, 0, n-1, l, r); }
    
    private long rangeQuery(int o, int s, int e, int l, int r) {
        if (r < s || e < l) return 0;
        if (l <= s && e <= r) return tree[o];
        int mid = (s + e) / 2;
        return rangeQuery(2*o, s, mid, l, r) + rangeQuery(2*o+1, mid+1, e, l, r);
    }
    
    public static void main(String[] args) {
        int[] arr = {1, 2, 3, 4, 5, 6, 7, 8};
        Problem46_SegmentTreeBuildAndQueryTemplate st = new Problem46_SegmentTreeBuildAndQueryTemplate(arr);
        System.out.println(st.rangeQuery(0, 7)); // 36
        System.out.println(st.rangeQuery(2, 5)); // 18
        st.pointUpdate(3, 10);
        System.out.println(st.rangeQuery(2, 5)); // 24
    }
}
