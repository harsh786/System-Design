package segmenttree;

/**
 * Problem 40: Lazy Range Add Range Max
 * 
 * Approach: Segment tree with lazy propagation for range add and range max query.
 * 
 * Time Complexity: O(log n) per operation
 * Space Complexity: O(n)
 */
public class Problem40_LazyRangeAddRangeMax {
    
    private long[] tree, lazy;
    private int n;
    
    public Problem40_LazyRangeAddRangeMax(int[] arr) {
        n = arr.length; tree = new long[4 * n]; lazy = new long[4 * n];
        build(1, 0, n - 1, arr);
    }
    
    private void build(int o, int s, int e, int[] arr) {
        if (s == e) { tree[o] = arr[s]; return; }
        int mid = (s + e) / 2;
        build(2 * o, s, mid, arr); build(2 * o + 1, mid + 1, e, arr);
        tree[o] = Math.max(tree[2 * o], tree[2 * o + 1]);
    }
    
    private void pushDown(int o) {
        if (lazy[o] != 0) {
            tree[2 * o] += lazy[o]; lazy[2 * o] += lazy[o];
            tree[2 * o + 1] += lazy[o]; lazy[2 * o + 1] += lazy[o];
            lazy[o] = 0;
        }
    }
    
    public void rangeAdd(int l, int r, long val) { rangeAdd(1, 0, n - 1, l, r, val); }
    
    private void rangeAdd(int o, int s, int e, int l, int r, long val) {
        if (r < s || e < l) return;
        if (l <= s && e <= r) { tree[o] += val; lazy[o] += val; return; }
        pushDown(o);
        int mid = (s + e) / 2;
        rangeAdd(2 * o, s, mid, l, r, val); rangeAdd(2 * o + 1, mid + 1, e, l, r, val);
        tree[o] = Math.max(tree[2 * o], tree[2 * o + 1]);
    }
    
    public long rangeMax(int l, int r) { return rangeMax(1, 0, n - 1, l, r); }
    
    private long rangeMax(int o, int s, int e, int l, int r) {
        if (r < s || e < l) return Long.MIN_VALUE;
        if (l <= s && e <= r) return tree[o];
        pushDown(o);
        int mid = (s + e) / 2;
        return Math.max(rangeMax(2 * o, s, mid, l, r), rangeMax(2 * o + 1, mid + 1, e, l, r));
    }
    
    public static void main(String[] args) {
        Problem40_LazyRangeAddRangeMax st = new Problem40_LazyRangeAddRangeMax(new int[]{1, 3, 5, 7, 9});
        System.out.println(st.rangeMax(0, 4)); // 9
        st.rangeAdd(0, 2, 10);
        System.out.println(st.rangeMax(0, 4)); // 15
    }
}
