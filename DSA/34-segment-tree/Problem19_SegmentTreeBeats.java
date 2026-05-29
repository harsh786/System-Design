package segmenttree;

/**
 * Problem 19: Segment Tree Beats (Ji Driver Segment Tree)
 * 
 * Approach: Supports "chmin" operation (set all elements to min(a[i], val)) and range sum/max queries.
 * Uses break/tag conditions based on max and second max of the segment.
 * 
 * Time Complexity: O(n log^2 n) amortized
 * Space Complexity: O(n)
 */
public class Problem19_SegmentTreeBeats {
    
    private long[] sum;
    private int[] mx, smx, cntMx;
    private int n;
    
    public Problem19_SegmentTreeBeats(int[] arr) {
        n = arr.length;
        sum = new long[4 * n]; mx = new int[4 * n]; smx = new int[4 * n]; cntMx = new int[4 * n];
        build(1, 0, n - 1, arr);
    }
    
    private void pushUp(int o) {
        int l = 2 * o, r = 2 * o + 1;
        sum[o] = sum[l] + sum[r];
        if (mx[l] == mx[r]) { mx[o] = mx[l]; cntMx[o] = cntMx[l] + cntMx[r]; smx[o] = Math.max(smx[l], smx[r]); }
        else if (mx[l] > mx[r]) { mx[o] = mx[l]; cntMx[o] = cntMx[l]; smx[o] = Math.max(smx[l], mx[r]); }
        else { mx[o] = mx[r]; cntMx[o] = cntMx[r]; smx[o] = Math.max(mx[l], smx[r]); }
    }
    
    private void build(int o, int s, int e, int[] arr) {
        if (s == e) { sum[o] = mx[o] = arr[s]; smx[o] = Integer.MIN_VALUE; cntMx[o] = 1; return; }
        int mid = (s + e) / 2;
        build(2 * o, s, mid, arr); build(2 * o + 1, mid + 1, e, arr);
        pushUp(o);
    }
    
    private void pushTag(int o, int val) {
        if (val >= mx[o]) return;
        sum[o] -= (long)(mx[o] - val) * cntMx[o];
        mx[o] = val;
    }
    
    private void pushDown(int o) { pushTag(2 * o, mx[o]); pushTag(2 * o + 1, mx[o]); }
    
    public void chmin(int l, int r, int val) { chmin(1, 0, n - 1, l, r, val); }
    
    private void chmin(int o, int s, int e, int l, int r, int val) {
        if (r < s || e < l || val >= mx[o]) return;
        if (l <= s && e <= r && val > smx[o]) { pushTag(o, val); return; }
        pushDown(o);
        int mid = (s + e) / 2;
        chmin(2 * o, s, mid, l, r, val); chmin(2 * o + 1, mid + 1, e, l, r, val);
        pushUp(o);
    }
    
    public long querySum(int l, int r) { return querySum(1, 0, n - 1, l, r); }
    
    private long querySum(int o, int s, int e, int l, int r) {
        if (r < s || e < l) return 0;
        if (l <= s && e <= r) return sum[o];
        pushDown(o);
        int mid = (s + e) / 2;
        return querySum(2 * o, s, mid, l, r) + querySum(2 * o + 1, mid + 1, e, l, r);
    }
    
    public int queryMax(int l, int r) { return queryMax(1, 0, n - 1, l, r); }
    
    private int queryMax(int o, int s, int e, int l, int r) {
        if (r < s || e < l) return Integer.MIN_VALUE;
        if (l <= s && e <= r) return mx[o];
        pushDown(o);
        int mid = (s + e) / 2;
        return Math.max(queryMax(2 * o, s, mid, l, r), queryMax(2 * o + 1, mid + 1, e, l, r));
    }
    
    public static void main(String[] args) {
        int[] arr = {5, 3, 8, 1, 7, 2, 9, 4};
        Problem19_SegmentTreeBeats st = new Problem19_SegmentTreeBeats(arr);
        System.out.println(st.querySum(0, 7)); // 39
        System.out.println(st.queryMax(0, 7)); // 9
        st.chmin(0, 7, 6);
        System.out.println(st.querySum(0, 7)); // 33 (8->6, 7->6, 9->6)
        System.out.println(st.queryMax(0, 7)); // 6
    }
}
