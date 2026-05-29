package segmenttree;

/**
 * Problem 15: Interval Assign Range Minimum
 * 
 * Approach: Segment tree with lazy propagation for range assignment and range min query.
 * Use sentinel value to indicate "no pending assignment".
 * 
 * Time Complexity: O(log n) per operation
 * Space Complexity: O(n)
 */
public class Problem15_IntervalAssignRangeMinimum {
    
    private long[] tree, lazy;
    private boolean[] hasLazy;
    private int n;
    
    public Problem15_IntervalAssignRangeMinimum(int[] arr) {
        n = arr.length;
        tree = new long[4 * n];
        lazy = new long[4 * n];
        hasLazy = new boolean[4 * n];
        build(1, 0, n - 1, arr);
    }
    
    private void build(int node, int s, int e, int[] arr) {
        if (s == e) { tree[node] = arr[s]; return; }
        int mid = (s + e) / 2;
        build(2 * node, s, mid, arr);
        build(2 * node + 1, mid + 1, e, arr);
        tree[node] = Math.min(tree[2 * node], tree[2 * node + 1]);
    }
    
    private void pushDown(int node) {
        if (hasLazy[node]) {
            for (int child : new int[]{2 * node, 2 * node + 1}) {
                tree[child] = lazy[node];
                lazy[child] = lazy[node];
                hasLazy[child] = true;
            }
            hasLazy[node] = false;
        }
    }
    
    public void rangeAssign(int l, int r, long val) { rangeAssign(1, 0, n - 1, l, r, val); }
    
    private void rangeAssign(int node, int s, int e, int l, int r, long val) {
        if (r < s || e < l) return;
        if (l <= s && e <= r) { tree[node] = val; lazy[node] = val; hasLazy[node] = true; return; }
        pushDown(node);
        int mid = (s + e) / 2;
        rangeAssign(2 * node, s, mid, l, r, val);
        rangeAssign(2 * node + 1, mid + 1, e, l, r, val);
        tree[node] = Math.min(tree[2 * node], tree[2 * node + 1]);
    }
    
    public long rangeMin(int l, int r) { return rangeMin(1, 0, n - 1, l, r); }
    
    private long rangeMin(int node, int s, int e, int l, int r) {
        if (r < s || e < l) return Long.MAX_VALUE;
        if (l <= s && e <= r) return tree[node];
        pushDown(node);
        int mid = (s + e) / 2;
        return Math.min(rangeMin(2 * node, s, mid, l, r), rangeMin(2 * node + 1, mid + 1, e, l, r));
    }
    
    public static void main(String[] args) {
        int[] arr = {5, 3, 8, 1, 7, 2};
        Problem15_IntervalAssignRangeMinimum st = new Problem15_IntervalAssignRangeMinimum(arr);
        System.out.println(st.rangeMin(0, 5)); // 1
        st.rangeAssign(2, 4, 10);
        System.out.println(st.rangeMin(0, 5)); // 2
        st.rangeAssign(0, 5, 4);
        System.out.println(st.rangeMin(0, 5)); // 4
    }
}
