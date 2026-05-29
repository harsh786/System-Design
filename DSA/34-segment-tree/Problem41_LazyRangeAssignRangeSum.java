package segmenttree;

/**
 * Problem 41: Lazy Range Assign Range Sum
 * 
 * Approach: Segment tree with lazy propagation for range assignment and range sum query.
 * 
 * Time Complexity: O(log n) per operation
 * Space Complexity: O(n)
 */
public class Problem41_LazyRangeAssignRangeSum {
    
    private long[] tree, lazy;
    private boolean[] hasLazy;
    private int n;
    
    public Problem41_LazyRangeAssignRangeSum(int[] arr) {
        n = arr.length; tree = new long[4 * n]; lazy = new long[4 * n]; hasLazy = new boolean[4 * n];
        build(1, 0, n - 1, arr);
    }
    
    private void build(int o, int s, int e, int[] arr) {
        if (s == e) { tree[o] = arr[s]; return; }
        int mid = (s + e) / 2;
        build(2 * o, s, mid, arr); build(2 * o + 1, mid + 1, e, arr);
        tree[o] = tree[2 * o] + tree[2 * o + 1];
    }
    
    private void pushDown(int o, int s, int e) {
        if (hasLazy[o]) {
            int mid = (s + e) / 2;
            apply(2 * o, s, mid, lazy[o]); apply(2 * o + 1, mid + 1, e, lazy[o]);
            hasLazy[o] = false;
        }
    }
    
    private void apply(int o, int s, int e, long val) {
        tree[o] = val * (e - s + 1); lazy[o] = val; hasLazy[o] = true;
    }
    
    public void rangeAssign(int l, int r, long val) { rangeAssign(1, 0, n - 1, l, r, val); }
    
    private void rangeAssign(int o, int s, int e, int l, int r, long val) {
        if (r < s || e < l) return;
        if (l <= s && e <= r) { apply(o, s, e, val); return; }
        pushDown(o, s, e);
        int mid = (s + e) / 2;
        rangeAssign(2 * o, s, mid, l, r, val); rangeAssign(2 * o + 1, mid + 1, e, l, r, val);
        tree[o] = tree[2 * o] + tree[2 * o + 1];
    }
    
    public long rangeSum(int l, int r) { return rangeSum(1, 0, n - 1, l, r); }
    
    private long rangeSum(int o, int s, int e, int l, int r) {
        if (r < s || e < l) return 0;
        if (l <= s && e <= r) return tree[o];
        pushDown(o, s, e);
        int mid = (s + e) / 2;
        return rangeSum(2 * o, s, mid, l, r) + rangeSum(2 * o + 1, mid + 1, e, l, r);
    }
    
    public static void main(String[] args) {
        Problem41_LazyRangeAssignRangeSum st = new Problem41_LazyRangeAssignRangeSum(new int[]{1, 2, 3, 4, 5});
        System.out.println(st.rangeSum(0, 4)); // 15
        st.rangeAssign(1, 3, 10);
        System.out.println(st.rangeSum(0, 4)); // 1+10+10+10+5=36
    }
}
