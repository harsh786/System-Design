package segmenttree;

/**
 * Problem 42: Segment Tree for LCM Range Query
 * 
 * Approach: LCM(a,b) = a*b / GCD(a,b). Store LCM in segment tree.
 * Note: values can overflow; use long.
 * 
 * Time Complexity: O(log n) per operation
 * Space Complexity: O(n)
 */
public class Problem42_SegmentTreeForLCMRangeQuery {
    
    private long[] tree;
    private int n;
    
    public Problem42_SegmentTreeForLCMRangeQuery(int[] arr) {
        n = arr.length; tree = new long[4 * n];
        build(1, 0, n - 1, arr);
    }
    
    private long gcd(long a, long b) { return b == 0 ? a : gcd(b, a % b); }
    private long lcm(long a, long b) { return a / gcd(a, b) * b; }
    
    private void build(int o, int s, int e, int[] arr) {
        if (s == e) { tree[o] = arr[s]; return; }
        int mid = (s + e) / 2;
        build(2 * o, s, mid, arr); build(2 * o + 1, mid + 1, e, arr);
        tree[o] = lcm(tree[2 * o], tree[2 * o + 1]);
    }
    
    public void update(int idx, int val) { update(1, 0, n - 1, idx, val); }
    
    private void update(int o, int s, int e, int idx, int val) {
        if (s == e) { tree[o] = val; return; }
        int mid = (s + e) / 2;
        if (idx <= mid) update(2 * o, s, mid, idx, val);
        else update(2 * o + 1, mid + 1, e, idx, val);
        tree[o] = lcm(tree[2 * o], tree[2 * o + 1]);
    }
    
    public long query(int l, int r) { return query(1, 0, n - 1, l, r); }
    
    private long query(int o, int s, int e, int l, int r) {
        if (r < s || e < l) return 1;
        if (l <= s && e <= r) return tree[o];
        int mid = (s + e) / 2;
        return lcm(query(2 * o, s, mid, l, r), query(2 * o + 1, mid + 1, e, l, r));
    }
    
    public static void main(String[] args) {
        Problem42_SegmentTreeForLCMRangeQuery st = new Problem42_SegmentTreeForLCMRangeQuery(new int[]{2, 3, 4, 5, 6});
        System.out.println(st.query(0, 4)); // 60
        System.out.println(st.query(0, 2)); // 12
        st.update(2, 7);
        System.out.println(st.query(0, 2)); // 42
    }
}
