package segmenttree;

import java.util.*;

/**
 * Problem 16: Maximum Segment Sum After Removals (LeetCode 2382)
 * 
 * Approach: Process removals in reverse (additions). Use segment tree tracking prefix sum, suffix sum,
 * total sum, and max segment sum for each node.
 * 
 * Time Complexity: O(n log n)
 * Space Complexity: O(n)
 */
public class Problem16_MaximumSegmentSumAfterRemovals {
    
    static long[] pref, suf, tot, best;
    
    static void pushUp(int node) {
        int l = 2 * node, r = 2 * node + 1;
        tot[node] = tot[l] + tot[r];
        pref[node] = Math.max(pref[l], tot[l] + pref[r]);
        suf[node] = Math.max(suf[r], tot[r] + suf[l]);
        best[node] = Math.max(Math.max(best[l], best[r]), suf[l] + pref[r]);
    }
    
    static void update(int node, int s, int e, int idx, long val) {
        if (s == e) { pref[node] = suf[node] = tot[node] = best[node] = val; return; }
        int mid = (s + e) / 2;
        if (idx <= mid) update(2 * node, s, mid, idx, val);
        else update(2 * node + 1, mid + 1, e, idx, val);
        pushUp(node);
    }
    
    public static long[] maxSegmentSum(int[] nums, int[] removeQueries) {
        int n = nums.length;
        pref = new long[4 * n]; suf = new long[4 * n]; tot = new long[4 * n]; best = new long[4 * n];
        long[] ans = new long[n];
        for (int i = n - 1; i >= 0; i--) {
            update(1, 0, n - 1, removeQueries[i], nums[removeQueries[i]]);
            if (i > 0) ans[i - 1] = Math.max(0, best[1]);
        }
        // ans[n-1] is after all removals = 0 (already 0)
        // shift: ans[i] = answer after i-th removal
        long[] result = new long[n];
        for (int i = 0; i < n; i++) {
            if (i == n - 1) result[i] = 0;
            else result[i] = ans[i];
        }
        return result;
    }
    
    public static void main(String[] args) {
        long[] res = maxSegmentSum(new int[]{1, 2, 5, 6, 1}, new int[]{0, 3, 2, 4, 1});
        System.out.println(Arrays.toString(res)); // [14, 7, 2, 2, 0]
    }
}
