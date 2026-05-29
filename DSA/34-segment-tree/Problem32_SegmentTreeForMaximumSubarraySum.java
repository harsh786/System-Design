package segmenttree;

/**
 * Problem 32: Segment Tree for Maximum Subarray Sum (with point updates)
 * 
 * Approach: Each node stores: total sum, max prefix, max suffix, max subarray sum.
 * 
 * Time Complexity: O(log n) per operation
 * Space Complexity: O(n)
 */
public class Problem32_SegmentTreeForMaximumSubarraySum {
    
    private long[] tot, pref, suf, best;
    private int n;
    
    public Problem32_SegmentTreeForMaximumSubarraySum(int[] arr) {
        n = arr.length;
        tot = new long[4 * n]; pref = new long[4 * n]; suf = new long[4 * n]; best = new long[4 * n];
        build(1, 0, n - 1, arr);
    }
    
    private void build(int o, int s, int e, int[] arr) {
        if (s == e) { tot[o] = pref[o] = suf[o] = best[o] = arr[s]; return; }
        int mid = (s + e) / 2;
        build(2 * o, s, mid, arr); build(2 * o + 1, mid + 1, e, arr);
        pushUp(o);
    }
    
    private void pushUp(int o) {
        int l = 2 * o, r = 2 * o + 1;
        tot[o] = tot[l] + tot[r];
        pref[o] = Math.max(pref[l], tot[l] + pref[r]);
        suf[o] = Math.max(suf[r], tot[r] + suf[l]);
        best[o] = Math.max(Math.max(best[l], best[r]), suf[l] + pref[r]);
    }
    
    public void update(int idx, int val) { update(1, 0, n - 1, idx, val); }
    
    private void update(int o, int s, int e, int idx, int val) {
        if (s == e) { tot[o] = pref[o] = suf[o] = best[o] = val; return; }
        int mid = (s + e) / 2;
        if (idx <= mid) update(2 * o, s, mid, idx, val);
        else update(2 * o + 1, mid + 1, e, idx, val);
        pushUp(o);
    }
    
    public long queryMaxSubarraySum() { return best[1]; }
    
    public static void main(String[] args) {
        Problem32_SegmentTreeForMaximumSubarraySum st = new Problem32_SegmentTreeForMaximumSubarraySum(new int[]{-2, 1, -3, 4, -1, 2, 1, -5, 4});
        System.out.println(st.queryMaxSubarraySum()); // 6
        st.update(7, 5);
        System.out.println(st.queryMaxSubarraySum()); // 15
    }
}
