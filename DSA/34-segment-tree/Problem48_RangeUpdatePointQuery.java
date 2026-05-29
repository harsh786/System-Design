package segmenttree;

/**
 * Problem 48: Range Update Point Query (using difference array + BIT/segment tree)
 * 
 * Approach: Use segment tree on difference array. Range add [l,r] by val means
 * diff[l] += val, diff[r+1] -= val. Point query = prefix sum = sum(0..idx).
 * 
 * Time Complexity: O(log n) per operation
 * Space Complexity: O(n)
 */
public class Problem48_RangeUpdatePointQuery {
    
    private long[] tree;
    private int n;
    
    public Problem48_RangeUpdatePointQuery(int[] arr) {
        n = arr.length; tree = new long[4 * n];
        // Build from original values (each is its own "prefix sum")
        // Store actual values; range update via lazy or use BIT on diff approach
        build(1, 0, n-1, arr);
    }
    
    private long[] lazy;
    { }
    
    public Problem48_RangeUpdatePointQuery(int n) {
        this.n = n; tree = new long[4*n]; lazy = new long[4*n];
    }
    
    private void build(int o, int s, int e, int[] arr) {
        lazy = new long[4*n];
        if (s == e) { tree[o] = arr[s]; return; }
        int mid = (s+e)/2;
        build(2*o, s, mid, arr); build(2*o+1, mid+1, e, arr);
        tree[o] = tree[2*o] + tree[2*o+1];
    }
    
    private void pushDown(int o, int s, int e) {
        if (lazy[o] != 0) {
            int mid = (s+e)/2;
            tree[2*o] += lazy[o]*(mid-s+1); lazy[2*o] += lazy[o];
            tree[2*o+1] += lazy[o]*(e-mid); lazy[2*o+1] += lazy[o];
            lazy[o] = 0;
        }
    }
    
    public void rangeAdd(int l, int r, long val) { rangeAdd(1, 0, n-1, l, r, val); }
    
    private void rangeAdd(int o, int s, int e, int l, int r, long val) {
        if (r < s || e < l) return;
        if (l <= s && e <= r) { tree[o] += val*(e-s+1); lazy[o] += val; return; }
        pushDown(o, s, e);
        int mid = (s+e)/2;
        rangeAdd(2*o, s, mid, l, r, val); rangeAdd(2*o+1, mid+1, e, l, r, val);
        tree[o] = tree[2*o] + tree[2*o+1];
    }
    
    public long pointQuery(int idx) { return pointQuery(1, 0, n-1, idx); }
    
    private long pointQuery(int o, int s, int e, int idx) {
        if (s == e) return tree[o];
        pushDown(o, s, e);
        int mid = (s+e)/2;
        if (idx <= mid) return pointQuery(2*o, s, mid, idx);
        return pointQuery(2*o+1, mid+1, e, idx);
    }
    
    public static void main(String[] args) {
        Problem48_RangeUpdatePointQuery st = new Problem48_RangeUpdatePointQuery(new int[]{1,2,3,4,5});
        st.rangeAdd(1, 3, 10);
        System.out.println(st.pointQuery(0)); // 1
        System.out.println(st.pointQuery(2)); // 13
        System.out.println(st.pointQuery(4)); // 5
    }
}
