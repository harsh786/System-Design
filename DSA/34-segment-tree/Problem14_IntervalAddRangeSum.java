package segmenttree;

/**
 * Problem 14: Interval Add Range Sum
 * 
 * Approach: Segment tree with lazy propagation supporting range add updates and range sum queries.
 * 
 * Time Complexity: O(log n) per operation
 * Space Complexity: O(n)
 */
public class Problem14_IntervalAddRangeSum {
    
    private long[] tree, lazy;
    private int n;
    
    public Problem14_IntervalAddRangeSum(int[] arr) {
        n = arr.length;
        tree = new long[4 * n];
        lazy = new long[4 * n];
        build(1, 0, n - 1, arr);
    }
    
    private void build(int node, int start, int end, int[] arr) {
        if (start == end) { tree[node] = arr[start]; return; }
        int mid = (start + end) / 2;
        build(2 * node, start, mid, arr);
        build(2 * node + 1, mid + 1, end, arr);
        tree[node] = tree[2 * node] + tree[2 * node + 1];
    }
    
    private void pushDown(int node, int start, int end) {
        if (lazy[node] != 0) {
            int mid = (start + end) / 2;
            tree[2 * node] += lazy[node] * (mid - start + 1);
            tree[2 * node + 1] += lazy[node] * (end - mid);
            lazy[2 * node] += lazy[node];
            lazy[2 * node + 1] += lazy[node];
            lazy[node] = 0;
        }
    }
    
    public void rangeAdd(int l, int r, long val) { rangeAdd(1, 0, n - 1, l, r, val); }
    
    private void rangeAdd(int node, int start, int end, int l, int r, long val) {
        if (r < start || end < l) return;
        if (l <= start && end <= r) {
            tree[node] += val * (end - start + 1);
            lazy[node] += val;
            return;
        }
        pushDown(node, start, end);
        int mid = (start + end) / 2;
        rangeAdd(2 * node, start, mid, l, r, val);
        rangeAdd(2 * node + 1, mid + 1, end, l, r, val);
        tree[node] = tree[2 * node] + tree[2 * node + 1];
    }
    
    public long rangeSum(int l, int r) { return rangeSum(1, 0, n - 1, l, r); }
    
    private long rangeSum(int node, int start, int end, int l, int r) {
        if (r < start || end < l) return 0;
        if (l <= start && end <= r) return tree[node];
        pushDown(node, start, end);
        int mid = (start + end) / 2;
        return rangeSum(2 * node, start, mid, l, r) + rangeSum(2 * node + 1, mid + 1, end, l, r);
    }
    
    public static void main(String[] args) {
        int[] arr = {1, 3, 5, 7, 9, 11};
        Problem14_IntervalAddRangeSum st = new Problem14_IntervalAddRangeSum(arr);
        System.out.println(st.rangeSum(1, 3)); // 15
        st.rangeAdd(1, 3, 10);
        System.out.println(st.rangeSum(1, 3)); // 45
    }
}
